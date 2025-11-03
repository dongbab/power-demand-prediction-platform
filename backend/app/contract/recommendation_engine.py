"""
계약전력 추천 엔진

최적화 결과를 기반으로 사용자 친화적 추천 생성
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from .optimizer import ContractOptimizer, OptimizationResult
from .cost_calculator import KEPCOCostCalculator


@dataclass
class ContractRecommendation:
    """계약전력 추천 결과"""
    # 기본 정보
    station_id: str
    analysis_date: str
    
    # 추천 계약전력
    recommended_contract_kw: int
    current_contract_kw: Optional[int]
    
    # 비용 분석
    expected_annual_cost: float
    expected_annual_savings: Optional[float]
    savings_percent: Optional[float]
    
    # 예측 정보
    predicted_peak_p50: float  # 중앙값
    predicted_peak_p95: float  # 95백분위
    
    # 리스크 분석
    overage_probability: float
    waste_probability: float
    confidence_level: float
    
    # 추천 사유
    recommendation_summary: str
    detailed_reasoning: List[str]
    
    # 액션 아이템
    action_required: bool
    urgency_level: str  # "high", "medium", "low"
    
    # 시각화 데이터
    cost_comparison_data: Dict[str, Any]
    candidate_analysis_data: List[Dict[str, Any]]


class RecommendationEngine:
    """
    계약전력 추천 엔진
    
    최적화 결과를 사용자 친화적인 추천으로 변환
    """
    
    def __init__(self):
        self.optimizer = ContractOptimizer()
        self.cost_calculator = KEPCOCostCalculator()
        self.logger = logging.getLogger(__name__)
    
    def generate_recommendation(
        self,
        station_id: str,
        prediction_distribution: Any,  # np.ndarray
        current_contract_kw: Optional[int] = None,
        **optimizer_kwargs
    ) -> ContractRecommendation:
        """
        계약전력 추천 생성
        
        Args:
            station_id: 충전소 ID
            prediction_distribution: 예측 피크 확률분포
            current_contract_kw: 현재 계약전력
            **optimizer_kwargs: 최적화 옵션
            
        Returns:
            ContractRecommendation: 추천 결과
        """
        import numpy as np
        
        self.logger.info(f"Station {station_id}: 계약전력 추천 생성 시작")
        
        # 1. 최적화 실행
        optimization = self.optimizer.optimize_contract(
            prediction_distribution,
            current_contract_kw,
            **optimizer_kwargs
        )
        
        # 2. 예측 통계 계산
        p50 = float(np.percentile(prediction_distribution, 50))
        p95 = float(np.percentile(prediction_distribution, 95))
        
        # 3. 상세 사유 생성
        detailed_reasoning = self._generate_detailed_reasoning(
            optimization,
            prediction_distribution
        )
        
        # 4. 액션 요구사항 판단
        action_required, urgency = self._assess_action_urgency(
            optimization,
            current_contract_kw
        )
        
        # 5. 시각화 데이터 준비
        cost_comparison = self._prepare_cost_comparison(
            optimization,
            current_contract_kw
        )
        
        candidate_analysis = self._prepare_candidate_analysis(
            optimization.all_candidates
        )
        
        recommendation = ContractRecommendation(
            station_id=station_id,
            analysis_date=datetime.now().isoformat(),
            recommended_contract_kw=optimization.optimal_contract_kw,
            current_contract_kw=current_contract_kw,
            expected_annual_cost=optimization.expected_annual_cost,
            expected_annual_savings=optimization.expected_savings,
            savings_percent=optimization.savings_percent,
            predicted_peak_p50=p50,
            predicted_peak_p95=p95,
            overage_probability=optimization.overage_probability,
            waste_probability=optimization.waste_probability,
            confidence_level=optimization.confidence_level,
            recommendation_summary=optimization.recommendation_reason,
            detailed_reasoning=detailed_reasoning,
            action_required=action_required,
            urgency_level=urgency,
            cost_comparison_data=cost_comparison,
            candidate_analysis_data=candidate_analysis
        )
        
        self.logger.info(
            f"Station {station_id}: 추천 완료 - {optimization.optimal_contract_kw}kW "
            f"(절감: {optimization.expected_savings:,.0f}원)" if optimization.expected_savings else ""
        )
        
        return recommendation
    
    def _generate_detailed_reasoning(
        self,
        optimization: OptimizationResult,
        distribution: Any
    ) -> List[str]:
        """상세 추천 사유 생성"""
        import numpy as np
        
        reasons = []
        
        # 1. 데이터 기반 분석
        sample_size = len(distribution)
        reasons.append(
            f"📊 {sample_size:,}개 예측 시나리오 분석 완료 "
            f"(신뢰도: {optimization.confidence_level:.0%})"
        )
        
        # 2. 예측 결과
        mean_peak = np.mean(distribution)
        std_peak = np.std(distribution)
        reasons.append(
            f"⚡ 예측 피크: 평균 {mean_peak:.0f}kW, "
            f"표준편차 ±{std_peak:.0f}kW"
        )
        
        # 3. 최적 계약 선정 이유
        optimal = optimization.optimal_candidate
        reasons.append(
            f"✅ 최적 계약 {optimal.contract_kw}kW 선정: "
            f"연간 비용 {optimal.expected_annual_cost:,.0f}원"
        )
        
        # 4. 리스크 평가
        if optimal.overage_probability < 5:
            risk_msg = f"🟢 초과 위험 매우 낮음 ({optimal.overage_probability:.1f}%)"
        elif optimal.overage_probability < 15:
            risk_msg = f"🟡 초과 위험 적정 ({optimal.overage_probability:.1f}%)"
        else:
            risk_msg = f"🔴 초과 위험 주의 ({optimal.overage_probability:.1f}%)"
        reasons.append(risk_msg)
        
        # 5. 절감 효과
        if optimization.expected_savings and optimization.expected_savings > 0:
            monthly_savings = optimization.expected_savings / 12
            reasons.append(
                f"💰 예상 절감: 연간 {optimization.expected_savings:,.0f}원 "
                f"(월 {monthly_savings:,.0f}원)"
            )
        
        # 6. 10kW 단위 최적화 강조
        reasons.append(
            f"🎯 10kW 단위 미세 조정으로 비용 최적화 달성"
        )
        
        return reasons
    
    def _assess_action_urgency(
        self,
        optimization: OptimizationResult,
        current_contract: Optional[int]
    ) -> tuple[bool, str]:
        """액션 긴급도 평가"""
        if current_contract is None:
            return True, "high"  # 신규 계약 필요
        
        if optimization.expected_savings is None:
            return False, "low"
        
        # 절감액 기준
        annual_savings = optimization.expected_savings
        
        if annual_savings > 1000000:  # 100만원 이상
            return True, "high"
        elif annual_savings > 500000:  # 50만원 이상
            return True, "medium"
        elif annual_savings > 100000:  # 10만원 이상
            return True, "low"
        elif annual_savings < -500000:  # 50만원 이상 손해
            return True, "high"  # 계약 상향 필요
        else:
            return False, "low"  # 현행 유지
    
    def _prepare_cost_comparison(
        self,
        optimization: OptimizationResult,
        current_contract: Optional[int]
    ) -> Dict[str, Any]:
        """비용 비교 데이터 준비 (차트용)"""
        if current_contract is None:
            return {
                "has_comparison": False,
                "recommended": {
                    "contract_kw": optimization.optimal_contract_kw,
                    "annual_cost": optimization.expected_annual_cost
                }
            }
        
        return {
            "has_comparison": True,
            "current": {
                "contract_kw": current_contract,
                "annual_cost": optimization.expected_annual_cost + (optimization.expected_savings or 0),
                "label": "현행 계약"
            },
            "recommended": {
                "contract_kw": optimization.optimal_contract_kw,
                "annual_cost": optimization.expected_annual_cost,
                "label": "추천 계약"
            },
            "savings": {
                "amount": optimization.expected_savings or 0,
                "percent": optimization.savings_percent or 0
            }
        }
    
    def _prepare_candidate_analysis(
        self,
        candidates: List[Any]  # List[ContractCandidate]
    ) -> List[Dict[str, Any]]:
        """후보 분석 데이터 준비 (차트용)"""
        return [
            {
                "contract_kw": c.contract_kw,
                "annual_cost": c.expected_annual_cost,
                "overage_probability": c.overage_probability,
                "waste_probability": c.waste_probability,
                "risk_score": c.risk_score
            }
            for c in sorted(candidates, key=lambda x: x.contract_kw)
        ]
    
    def to_dict(self, recommendation: ContractRecommendation) -> Dict[str, Any]:
        """추천 결과를 딕셔너리로 변환 (API 응답용)"""
        result = asdict(recommendation)
        
        # annual_savings_won 키 추가 (하위 호환성)
        if recommendation.expected_annual_savings:
            result['annual_savings_won'] = recommendation.expected_annual_savings
            result['monthly_savings'] = recommendation.expected_annual_savings / 12
        
        # savings_percentage 키 추가
        if recommendation.current_contract_kw and recommendation.expected_annual_savings:
            current_annual_cost = recommendation.current_contract_kw * 8320 * 12
            result['savings_percentage'] = (
                recommendation.expected_annual_savings / current_annual_cost * 100
                if current_annual_cost > 0 else 0
            )
        
        # recommendation 키 추가 (추천 요약문)
        result['recommendation'] = recommendation.recommendation_summary
        
        # risk_assessment 키 추가
        result['risk_assessment'] = {
            'risk_level': recommendation.urgency_level,
            'overage_probability': recommendation.overage_probability,
            'waste_probability': recommendation.waste_probability,
            'confidence_level': recommendation.confidence_level
        }
        
        return result
