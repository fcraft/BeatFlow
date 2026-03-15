"""运动生理模型单元测试。"""
import pytest
from app.engine.exercise_physiology import ExercisePhysiologyModel


class TestExercisePhysiologyModel:
    """运动心率响应模型测试。"""

    def _make_model(self, **kwargs) -> ExercisePhysiologyModel:
        defaults = dict(age=30, fitness_level=0.5, resting_hr=72.0)
        defaults.update(kwargs)
        return ExercisePhysiologyModel(**defaults)

    def test_hr_max_formula(self):
        """HR_max = 208 - 0.7 × age (Tanaka 公式)。"""
        m = self._make_model(age=30)
        assert m.hr_max == pytest.approx(187.0)

    def test_hr_reserve(self):
        """HR_reserve = HR_max - resting_hr。"""
        m = self._make_model(age=30, resting_hr=72.0)
        assert m.hr_reserve == pytest.approx(115.0)

    def test_rest_returns_zero_contribution(self):
        """intensity=0 时运动 HR 贡献为 0。"""
        m = self._make_model()
        hr_delta = m.compute_hr_delta(intensity=0.0, elapsed_sec=0.0, fatigue=0.0, dehydration=0.0)
        assert hr_delta == pytest.approx(0.0, abs=1.0)

    def test_walk_hr_delta_range(self):
        """步行 (0.3) 起始阶段 HR 增量应在 20-40 bpm。"""
        m = self._make_model(fitness_level=0.5)
        hr_delta = m.compute_hr_delta(intensity=0.3, elapsed_sec=30.0, fatigue=0.0, dehydration=0.0)
        assert 20.0 <= hr_delta <= 40.0

    def test_run_hr_delta_range(self):
        """跑步 (0.8) 起始阶段 HR 增量应在 50-80 bpm。"""
        m = self._make_model(fitness_level=0.5)
        hr_delta = m.compute_hr_delta(intensity=0.8, elapsed_sec=30.0, fatigue=0.0, dehydration=0.0)
        assert 50.0 <= hr_delta <= 80.0

    def test_cardiac_drift_increases_hr_over_time(self):
        """相同强度下，运动 20 分钟后 HR 应比 1 分钟时高。"""
        m = self._make_model()
        hr_1min = m.compute_hr_delta(intensity=0.6, elapsed_sec=60.0, fatigue=0.0, dehydration=0.0)
        hr_20min = m.compute_hr_delta(intensity=0.6, elapsed_sec=1200.0, fatigue=0.0, dehydration=0.0)
        assert hr_20min > hr_1min + 3.0

    def test_cardiac_drift_saturates(self):
        """心率漂移有上限，不能无限增长。"""
        m = self._make_model()
        hr_20min = m.compute_hr_delta(intensity=0.6, elapsed_sec=1200.0, fatigue=0.0, dehydration=0.0)
        hr_60min = m.compute_hr_delta(intensity=0.6, elapsed_sec=3600.0, fatigue=0.0, dehydration=0.0)
        assert hr_60min - hr_20min < 10.0

    def test_higher_fitness_lower_hr(self):
        """体能好的人相同强度 HR 更低。"""
        m_fit = self._make_model(fitness_level=0.9)
        m_unfit = self._make_model(fitness_level=0.2)
        hr_fit = m_fit.compute_hr_delta(intensity=0.6, elapsed_sec=60.0, fatigue=0.0, dehydration=0.0)
        hr_unfit = m_unfit.compute_hr_delta(intensity=0.6, elapsed_sec=60.0, fatigue=0.0, dehydration=0.0)
        assert hr_unfit > hr_fit + 10.0

    def test_fatigue_increases_hr(self):
        """疲劳状态下相同运动 HR 更高。"""
        m = self._make_model()
        hr_fresh = m.compute_hr_delta(intensity=0.5, elapsed_sec=60.0, fatigue=0.0, dehydration=0.0)
        hr_fatigued = m.compute_hr_delta(intensity=0.5, elapsed_sec=60.0, fatigue=0.7, dehydration=0.0)
        assert hr_fatigued > hr_fresh + 5.0

    def test_dehydration_increases_hr(self):
        """脱水导致 HR 升高。"""
        m = self._make_model()
        hr_hydrated = m.compute_hr_delta(intensity=0.5, elapsed_sec=60.0, fatigue=0.0, dehydration=0.0)
        hr_dehydrated = m.compute_hr_delta(intensity=0.5, elapsed_sec=60.0, fatigue=0.0, dehydration=0.6)
        assert hr_dehydrated > hr_hydrated + 3.0

    def test_hr_delta_capped_by_hr_reserve(self):
        """HR 增量不超过 HR_reserve。"""
        m = self._make_model(age=30, resting_hr=72.0)
        hr_delta = m.compute_hr_delta(intensity=1.0, elapsed_sec=3600.0, fatigue=1.0, dehydration=1.0)
        assert hr_delta <= m.hr_reserve

    def test_fatigue_accumulation(self):
        """运动会累积疲劳，强度越高累积越快。"""
        m = self._make_model()
        f1 = m.compute_fatigue_delta(intensity=0.3, dt=60.0, current_fatigue=0.0)
        f2 = m.compute_fatigue_delta(intensity=0.8, dt=60.0, current_fatigue=0.0)
        assert f2 > f1 > 0.0

    def test_fatigue_recovery_at_rest(self):
        """静息时疲劳恢复（负增量）。"""
        m = self._make_model()
        f = m.compute_fatigue_delta(intensity=0.0, dt=60.0, current_fatigue=0.5)
        assert f < 0.0

    def test_recovery_hr_has_fast_and_slow_phase(self):
        """运动后恢复 HR 应有快速和慢速两个阶段。"""
        m = self._make_model()
        tau_fast, tau_slow, fast_fraction = m.get_recovery_time_constants(
            pre_exercise_hr_delta=60.0, fatigue=0.3
        )
        assert tau_fast < tau_slow
        assert 0.4 <= fast_fraction <= 0.85
