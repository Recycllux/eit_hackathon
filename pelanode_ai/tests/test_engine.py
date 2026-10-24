import logging
from src.data.loader import DanubeDataLoader
from src.analytics.propagation import PropagationAnalyzer
from src.analytics.anomaly import TemperatureAnomalyDetector

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def run_validations():
    # 1. Load the aligned dataset
    loader = DanubeDataLoader()
    df_matrix = loader.get_normalized_danube_matrix()

    print("\n" + "=" * 50)
    print("🧪 RUNNING DATA SCIENCE VALIDATIONS (P0-19 §12.6)")
    print("=" * 50)

    # ---------------------------------------------------------
    # TEST 1: Hydrological Propagation Engine
    # ---------------------------------------------------------
    print("\n--- Testing PropagationAnalyzer ---")
    prop_engine = PropagationAnalyzer(df_matrix)

    # Check Calafat -> Bechet (Expected: Lag 1, r_Ah ~0.888, Class A)
    bechet_res = prop_engine.analyze_pair('Calafat', 'Bechet')
    print(f"Calafat -> Bechet:")
    print(f"  Level Lag: {bechet_res['optimal_lag_days_level']}d | Ah Lag: {bechet_res['optimal_lag_days_delta_h']}d")
    print(f"  r_Ah: {bechet_res['r_delta_h']} | Class: {bechet_res['quality_class']}")
    assert bechet_res['quality_class'] == 'A', "Failed: Should be Class A"
    assert round(bechet_res['r_delta_h'], 2) == 0.89, "Failed: r_Ah should round to 0.89"

    # Check Calafat -> Giurgiu (Expected: Level Lag 3, Ah Lag 2)
    giurgiu_res = prop_engine.analyze_pair('Calafat', 'Giurgiu')
    print(f"\nCalafat -> Giurgiu:")
    print(f"  Level Lag: {giurgiu_res['optimal_lag_days_level']}d | Ah Lag: {giurgiu_res['optimal_lag_days_delta_h']}d")
    assert giurgiu_res['optimal_lag_days_level'] == 3, "Failed: Level lag should be 3"
    assert giurgiu_res['optimal_lag_days_delta_h'] == 2, "Failed: Ah lag should be 2"

    # Check Lom -> Nikopol (Expected: Class C due to gaps)
    nikopol_res = prop_engine.analyze_pair('Lom', 'Nikopol')
    print(f"\nLom -> Nikopol:")
    print(f"  Class: {nikopol_res['quality_class']} | Reason: {nikopol_res['note']}")
    assert nikopol_res['quality_class'] == 'C', "Failed: Should be Class C"

    # ---------------------------------------------------------
    # TEST 2: Temperature Anomaly Engine
    # ---------------------------------------------------------
    print("\n--- Testing TemperatureAnomalyDetector ---")
    anomaly_engine = TemperatureAnomalyDetector(df_matrix)
    candidates_df = anomaly_engine.compute_scores()

    # Filter for Gorni Vadin primary anomalies (Expected: 5)
    gorni_primary = candidates_df[(candidates_df['station'] == 'Gorni Vadin') &
                                  (candidates_df['role'] == 'primary')]

    # Filter for Kozloduy influenced anomalies (Expected: 4)
    kozloduy_influenced = candidates_df[(candidates_df['station'] == 'Kozloduy') &
                                        (candidates_df['role'] == 'neighbour_influenced')]

    # Filter for Zagrazhden on 2021-06-08 (Expected: 1)
    zagrazhden_june8 = candidates_df[(candidates_df['station'] == 'Zagrazhden') &
                                     (candidates_df['date'] == '2021-06-08')]

    print(f"Gorni Vadin Primary Candidates: {len(gorni_primary)} (Expected: 5)")
    print(f"Kozloduy Influenced Candidates: {len(kozloduy_influenced)} (Expected: 4)")
    print(f"Zagrazhden Primary on June 8: {len(zagrazhden_june8)} (Expected: 1)")

    assert len(gorni_primary) == 5, "Failed: Gorni Vadin should have exactly 5 primary candidates"
    assert len(kozloduy_influenced) == 4, "Failed: Kozloduy should have exactly 4 influenced candidates"
    assert len(zagrazhden_june8) == 1, "Failed: Zagrazhden should have a flag on June 8, 2021"

    print("\n" + "=" * 50)
    print("✅ ALL DATA SCIENCE TESTS PASSED PERFECTLY!")
    print("=" * 50)


if __name__ == "__main__":
    run_validations()