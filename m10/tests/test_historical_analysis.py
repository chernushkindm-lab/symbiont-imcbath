from datetime import datetime,timedelta,timezone
import unittest
from metabocore.historical_analysis import analyze_observations


def obs(i,value,code='dry_residue_g_L',**changes):
    r={'observation_id':f'{code}-{i}','run_id':'r','segment_id':'s','parameter_code':code,
       'event_time':(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(),
       'value':value,'unit':'g/L' if code!='legacy_dilution_h_inv' else '1/h',
       'classification':'recalculated','accepted':True,'calibration_version':'k1',
       'availability_time':None,'source_locator':{'source_id':'fixture','sheet':'x','row':i+1},'qc_flags':[]}
    return r|changes


class HistoricalAnalysisTest(unittest.TestCase):
    def test_real_endpoint_algebra_and_true_ids(self):
        records=[obs(0,2),obs(2,3),obs(2,.2,'legacy_dilution_h_inv'),obs(2,5,'legacy_asv_g_L')]
        result=analyze_observations(records)
        interval=result['residue_intervals'][0]
        self.assertEqual(interval['net_inventory_accumulation_g_h'],5)
        self.assertEqual(interval['parent_observation_ids'],['dry_residue_g_L-0','dry_residue_g_L-2'])
        self.assertIsNone(interval['net_biological_formation_g_l_h'])
        self.assertAlmostEqual(result['dilution_productivity_proxies'][0]['dilution_residue_proxy_g_l_h'],.6)
        self.assertEqual(result['legacy_comparisons'][0]['selected_minus_legacy_g_l'],-2)
        self.assertIsNone(interval['availability_time'])

    def test_no_nearest_dilution_or_segment_bridge(self):
        result=analyze_observations([obs(0,2),obs(1,3,segment_id='other'),obs(2,.2,'legacy_dilution_h_inv')])
        self.assertEqual(result['residue_intervals'],[])
        self.assertEqual(result['dilution_productivity_proxies'],[])

    def test_no_calibration_or_invalid_point_bridge(self):
        result=analyze_observations([obs(0,1),obs(1,2,calibration_version='k2'),obs(2,3)])
        self.assertEqual(result['residue_intervals'],[])
        result=analyze_observations([obs(0,1),obs(1,2,accepted=False),obs(2,3)])
        self.assertEqual(result['residue_intervals'],[])

    def test_shared_calibration_interval_applies_to_difference(self):
        result=analyze_observations([obs(0,10),obs(1,9)],calibration_intervals={
            'k1':{'coefficient':1,'coefficient_interval':[.9,1.1],'source':'fixture'}})
        bound=result['residue_intervals'][0]['uncertainty']
        self.assertEqual(bound['lower_g_h'],-11)
        self.assertEqual(bound['upper_g_h'],-9)
        # Independent endpoint bounds would exaggerate this small difference.
        self.assertTrue(bound['not_total_prediction_interval'])

    def test_duplicate_id_and_large_gap_rejected(self):
        with self.assertRaises(ValueError):
            analyze_observations([obs(0,1),obs(0,1)])
        result=analyze_observations([obs(0,1),obs(12,2)])
        self.assertEqual(result['residue_intervals'],[])
        self.assertEqual(result['summary']['exclusion_counts']['nonpositive_or_excessive_interval'],1)


class HypothesisLinkTest(unittest.TestCase):
    def test_links_reference_existing_records_without_claiming_cause(self):
        from metabocore.historical_analysis import build_hypotheses
        records=[obs(0,1),obs(1,-1,'legacy_feed_ml_min',qc_flags=['negative_inferred_delivery']),
                 obs(2,80,'offgas_o2_pct',qc_flags=['invalid_gas_composition_sum']),
                 obs(3,None,'rapid_po4_mg_L',qc_flags=['censored'])]
        run={'run_id':'r','observations':records,'events':[{'event_id':'e1','kind':'bottle_label_change',
             'boundary':True,'event_time':records[0]['event_time'],'description':'Bottle A changed',
             'source_locator':{'row':4}}]}
        hypotheses=build_hypotheses(run)
        self.assertEqual(len(hypotheses),8)
        known={r['observation_id'] for r in records}
        for h in hypotheses:
            self.assertTrue(set(h['parent_observation_ids'])<=known)
            self.assertIn(h['confidence'],{'unresolved','no_linked_evidence'})
            self.assertIn('not a causal',h['ordering_meaning'])
        nutrient=next(h for h in hypotheses if h['hypothesis_id'].endswith('nutrients'))
        self.assertIn(records[3]['observation_id'],nutrient['parent_observation_ids'])


if __name__=='__main__':
    unittest.main()
