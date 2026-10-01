from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import exp
import unittest

from metabocore.balances import (Interval, Stream, inventory_balance, biomass_productivity,
                                bottle_delivery_l_h, gas_volume_to_mmol_h, gas_fluxes,
                                conditional_exhaust_flow, tracer_exhaust_flow, oxygen_transfer,
                                do_air_saturation_to_mmol_l, element_mmol_from_solution)
from metabocore.kinetics import (KineticParameters, BoundaryConditions, LiquidEvent, rhs,
                                apply_event, simulate, kinetic_reference_case)
from metabocore.evaluation import (ForecastPair, evaluate_pairs, assert_no_future_information,
                                  rolling_origin_baselines, capacity_gap)


class PhysicalBalancesTest(unittest.TestCase):
    def test_variable_volume_inventory_and_elapsed_time(self):
        b = inventory_balance(volume_start_l=8, volume_end_l=10, concentration_start=2,
                              concentration_end=3, elapsed_h=2, incoming=[Stream(1,10,basis='mmol/L')],
                              outgoing=[Stream(.5,3,basis='mmol/L')])
        self.assertEqual(b['accumulation_per_h'], 7)
        self.assertEqual(b['apparent_disappearance_per_h'], 1.5)

    def test_sampling_impulse_counted_once(self):
        b = inventory_balance(volume_start_l=10, volume_end_l=9, concentration_start=2,
                              concentration_end=2, elapsed_h=2, incoming=[], outgoing=[], removed_quantity=2)
        self.assertEqual(b['apparent_disappearance_per_h'], 0)

    def test_drain_refill_residue_not_growth(self):
        b = biomass_productivity(volume_start_l=10, volume_end_l=10,
                                 concentration_start_g_l=2, concentration_end_g_l=1,
                                 elapsed_h=2, incoming=[], outgoing=[], removed_mass_g=10,
                                 mean_volume_l=10, harvested_mass_g=10)
        self.assertEqual(b['net_formation_g_l_h'], 0)
        self.assertEqual(b['harvest_productivity_g_l_h'], .5)
        self.assertFalse(b['cellular_interpretation_supported'])

    def test_missing_and_mixed_units_rejected(self):
        with self.assertRaises(ValueError):
            inventory_balance(volume_start_l=10, volume_end_l=10, concentration_start=None,
                              concentration_end=1, elapsed_h=1, incoming=[], outgoing=[])
        with self.assertRaises(ValueError):
            inventory_balance(volume_start_l=10, volume_end_l=10, concentration_start=1,
                              concentration_end=1, elapsed_h=1, incoming=[Stream(1,2)], outgoing=[])

    def test_bottle_reset_not_negative_delivery(self):
        self.assertIsNone(bottle_delivery_l_h(100,200,1,1)['flow_l_h'])
        self.assertAlmostEqual(bottle_delivery_l_h(200,100,2,1)['flow_l_h'], .05)

    def test_elemental_basis_density_purity(self):
        self.assertAlmostEqual(element_mmol_from_solution(1,1.5,.5,100,2),15)

    def test_ideal_gas_units(self):
        value = gas_volume_to_mmol_h(22.41396954,pressure_atm=1,temperature_k=273.15,volume_basis='normal')
        self.assertAlmostEqual(value,1000,places=3)

    def test_invalid_gas_never_renormalized(self):
        r = gas_fluxes({'CH4':100,'O2':100,'CO2':0},{'CH4':.7,'O2':.6,'CO2':.1},
                       exhaust_mmol_h=100,exhaust_evidence='test',inventory_plus_liquid_correction_mmol_h={'CH4':0,'O2':0,'CO2':0})
        self.assertEqual(r['status'],'blocked')
        self.assertIn('gas_composition_sum_above_one',r['reasons'])

    def test_inlet_does_not_identify_exhaust(self):
        self.assertEqual(conditional_exhaust_flow(Interval(99,101))['status'],'not_identifiable')
        r = conditional_exhaust_flow(Interval(100,100),methane_uptake_mmol_h=Interval(10,20),
                                     oxygen_uptake_mmol_h=Interval(20,30),co2_generation_mmol_h=Interval(5,10),
                                     total_inventory_change_mmol_h=Interval(0,0),assumptions=['synthetic closure'])
        self.assertEqual(r['status'],'model_only')
        self.assertEqual(r['exhaust_mmol_h'],{'lower':55,'upper':80})

    def test_nitrogen_tracer_requires_conservation(self):
        r = tracer_exhaust_flow(Interval(80,80),Interval(.4,.4),conservation_evidence='generic inert claim',
                                inventory_and_leak_correction_mmol_h=Interval(0,0),nitrogen_included=True)
        self.assertEqual(r['status'],'blocked')

    def test_gas_signs_ratios_and_inventory(self):
        r = gas_fluxes({'CH4':100,'O2':150,'CO2':0},{'CH4':.1,'O2':.2,'CO2':.1},
                       exhaust_mmol_h=200,exhaust_evidence='synthetic calibration',
                       inventory_plus_liquid_correction_mmol_h={'CH4':10,'O2':10,'CO2':5})
        self.assertEqual((r['MUR'],r['OUR'],r['CER']),(70,100,25))
        self.assertEqual(r['RQ_CER_over_OUR'],.25)

    def test_transfer_total_vs_volumetric(self):
        r = oxygen_transfer(700,.2,.1,10)
        self.assertEqual(r,{'volumetric_mmol_l_h':70,'total_mmol_h':700})
        self.assertAlmostEqual(do_air_saturation_to_mmol_l(50,calibrated_air_saturation_mg_l=8),4/31.998)


class KineticNumericsTest(unittest.TestCase):
    def setUp(self):
        self.p = KineticParameters(.2,.01,.01,.5,.25,.5)
        self.b = BoundaryConditions(*([0.]*15))

    def test_rhs_pure_and_coupled_demands(self):
        state=[1,.1,.2,0,10]
        a=rhs(0,state,self.p,self.b)
        rhs(100,[2,.2,.1,.1,10],self.p,self.b)
        self.assertEqual(a,rhs(0,state,self.p,self.b))
        self.assertAlmostEqual(-a[1]*self.p.yield_x_ch4_g_g,a[0])
        self.assertAlmostEqual(-a[2]*self.p.yield_x_o2_g_g,a[0])
        self.assertEqual(state,[1,.1,.2,0,10])

    def test_no_substrate_no_growth(self):
        self.assertEqual(rhs(0,[1,0,.2,0,10],self.p,self.b)[0],0)
        self.assertEqual(rhs(0,[1,.1,0,0,10],self.p,self.b)[0],0)

    def test_carbon_conservation_rhs(self):
        dx,dch4,_,dco2,_=rhs(0,[1,.1,.2,0,10],self.p,self.b)
        self.assertAlmostEqual(dx*.5+dch4*12.011/16.043+dco2*12.011/44.009,0,places=12)

    def test_gas_stripping_preserved(self):
        b=replace(self.b,kla_co2_h=2,cstar_co2_g_l=.01)
        self.assertLess(rhs(0,[0,0,0,.1,10],self.p,b)[3],0)

    def test_drain_refill_event_mass(self):
        event=LiquidEvent(1,2,2)
        state=apply_event([1,.1,.2,.3,10],event)
        self.assertEqual(state[0],.8)
        self.assertEqual(state[4],10)
        result=simulate([1,0,0,0,10],[0,1,2],self.p,self.b,events=[event])
        self.assertAlmostEqual(result['states'][1][0],.8)
        self.assertAlmostEqual(result['states'][2][0],.8)

    def test_volume_inventory_with_nonselective_outflow(self):
        b=replace(self.b,outflow_l_h=1)
        result=simulate([1,0,0,0,10],[0,1,2],self.p,b)
        self.assertAlmostEqual(result['states'][-1][0],1)
        self.assertAlmostEqual(result['states'][-1][4],8)

    def test_analytic_washout_and_convergence(self):
        b=replace(self.b,feed_l_h=1,outflow_l_h=1)
        coarse=simulate([1,0,0,0,10],[0,4],self.p,b,rtol=1e-5)
        fine=simulate([1,0,0,0,10],[0,4],self.p,b,rtol=1e-9)
        expected=exp(-.4)
        self.assertLess(abs(fine['states'][-1][0]-expected),2e-8)
        self.assertLess(abs(fine['states'][-1][0]-expected),abs(coarse['states'][-1][0]-expected))

    def test_reference_nonnegative_and_carbon_conserved(self):
        result=kinetic_reference_case()
        self.assertLess(result['conservation']['maximum_carbon_residual_g'],1e-8)
        self.assertTrue(all(x>=0 for state in result['states'] for x in state))
        self.assertFalse(result['historical_validation'])


class ForecastValidityTest(unittest.TestCase):
    def test_future_availability_rejected_even_if_old_sample(self):
        with self.assertRaises(ValueError):
            assert_no_future_information('2026-01-01T02:00:00+00:00',
                                         [{'timestamp':'2026-01-01T00:00:00+00:00','available_at':'2026-01-01T03:00:00+00:00'}])

    def test_irregular_weighting_and_variable_volume_mass(self):
        pair=ForecastPair('r','s','2026-01-01T01:00:00+00:00','2026-01-01T02:00:00+00:00',
                          '2026-01-01T00:00:00+00:00','harvest_productivity_g_l_h','harvest_productivity_g_l_h',1,2,'m','a',mean_volume_l=10)
        second=replace(pair,interval_start='2026-01-01T04:00:00+00:00',interval_end='2026-01-01T06:00:00+00:00',
                       forecast_origin='2026-01-01T04:00:00+00:00',observed=1,predicted=3,evidence_id='b',mean_volume_l=5)
        metrics=evaluate_pairs([pair,second])['metrics'][0]
        self.assertAlmostEqual(metrics['time_weighted_mae'],5/3)
        self.assertEqual(metrics['integrated_harvest_mass_difference_g'],30)

    def test_synthetic_constraint_and_observable_exclusions(self):
        p=ForecastPair('r','s','2026-01-01T00:00:00+00:00','2026-01-01T01:00:00+00:00',
                       '2026-01-01T00:00:00+00:00','residue','cellular_dcw',1,2,'m','a')
        self.assertEqual(evaluate_pairs([p])['excluded'][0]['reason'],'observable_mismatch')
        p=replace(p,predicted_observable='residue',used_as_constraint=True)
        self.assertEqual(evaluate_pairs([p])['included_count'],0)
        self.assertIsNone(capacity_gap(2,0)['relative_to_observed_percent'])

    def test_baselines_no_future_leakage_or_cross_segment_pooling(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        records=[{'run_id':'r','segment_id':'s','timestamp':(start+timedelta(hours=i)).isoformat(),
                  'available_at':(start+timedelta(hours=i)).isoformat(),'value':exp(.01*i),'evidence_id':str(i)} for i in range(20)]
        result=rolling_origin_baselines(records,horizons_h=(1,),minimum_training=5)
        rows=[r for r in result['predictions'] if r['model']=='training_log_linear']
        self.assertTrue(rows)
        self.assertLess(max(r['absolute_error'] for r in rows),1e-12)
        for r in rows:
            self.assertLessEqual(r['input_availability_max'],r['forecast_origin'])
        altered=[dict(r) for r in records]
        altered[-1]['value']=1e9
        changed=rolling_origin_baselines(altered,horizons_h=(1,),minimum_training=5)
        self.assertEqual(result['predictions'][0]['predicted'],changed['predictions'][0]['predicted'])
        for r in records[5:]:
            r['segment_id']='other'
        result=rolling_origin_baselines(records,horizons_h=(1,),minimum_training=5)
        self.assertTrue(all(len(r['input_evidence_ids'])>=5 for r in result['predictions']))



class UncertaintyGatesTest(unittest.TestCase):
    def test_censored_loss_does_not_invent_midpoint(self):
        from metabocore.evaluation import censored_interval_loss
        self.assertEqual(censored_interval_loss(5, 1, 10), 0)
        self.assertEqual(censored_interval_loss(12, 1, 10, scale=2), 1)
        self.assertEqual(censored_interval_loss(2, None, 3), 0)

    def test_residue_is_not_cellular_mass(self):
        from metabocore.balances import specific_cellular_uptake
        r = specific_cellular_uptake(Interval(10,20), Interval(5,10),
                                     cellular_sink_supported=True, cellular_mass_supported=False)
        self.assertEqual(r['status'], 'blocked')
        r = specific_cellular_uptake(Interval(10,20), Interval(5,10),
                                     cellular_sink_supported=True, cellular_mass_supported=True)
        self.assertEqual(r['q_mmol_g_h'], {'lower': 1., 'upper': 4.})

    def test_unknown_availability_is_explicit_exclusion(self):
        r = rolling_origin_baselines([{'value': 1., 'evidence_id': 'unknown', 'available_at': None}])
        self.assertEqual(r['predictions'], [])
        self.assertEqual(r['blocked'][0]['reason'], 'availability_unknown')


if __name__ == '__main__':
    unittest.main()
