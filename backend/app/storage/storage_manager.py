import hashlib
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from datetime import datetime

from .prediction_db import PredictionDatabase

logger = logging.getLogger(__name__)

class StorageManager:
    """예측 결과 저장 관리자 - 다중 저장 방식 지원"""
    
    def __init__(self, use_database: bool = True, base_path: str = "data"):
        self.use_database = use_database
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 데이터베이스 초기화
        if use_database:
            self.db = PredictionDatabase(str(self.base_path / "predictions.db"))
        else:
            self.db = None
            
        # 파일 저장 경로
        self.file_storage_path = self.base_path / "predictions"
        self.file_storage_path.mkdir(exist_ok=True)
        
    def generate_file_hash(self, file_content: bytes) -> str:
        """파일 해시 생성"""
        return hashlib.sha256(file_content).hexdigest()[:16]
    
    def save_prediction(self, station_id: str, prediction_data: Dict[str, Any], 
                       file_hash: str = None) -> bool:
        """예측 결과 저장 (DB + 파일 백업)"""
        success = True
        
        # 데이터베이스에 저장
        if self.db:
            try:
                success &= self.db.save_prediction(station_id, prediction_data, file_hash)
                logger.info(f"Saved prediction to database: {station_id}")
            except Exception as e:
                logger.error(f"Database save failed for {station_id}: {e}")
                success = False
        
        # 파일 백업 저장
        try:
            self._save_to_file(station_id, prediction_data, file_hash)
            logger.debug(f"Backed up prediction to file: {station_id}")
        except Exception as e:
            logger.warning(f"File backup failed for {station_id}: {e}")
            # 파일 저장 실패는 전체 실패로 간주하지 않음
            
        return success
    
    def load_prediction(self, station_id: str, file_hash: str = None) -> Optional[Dict[str, Any]]:
        """예측 결과 로드 (DB 우선, 파일 폴백)"""
        # 데이터베이스에서 먼저 시도
        if self.db:
            try:
                result = self.db.load_prediction(station_id, file_hash)
                if result:
                    logger.debug(f"Loaded prediction from database: {station_id}")
                    return result
            except Exception as e:
                logger.warning(f"Database load failed for {station_id}: {e}")
        
        # 파일에서 폴백 시도
        try:
            result = self._load_from_file(station_id, file_hash)
            if result:
                logger.info(f"Loaded prediction from file backup: {station_id}")
                return result
        except Exception as e:
            logger.warning(f"File load failed for {station_id}: {e}")
            
        logger.warning(f"No prediction found for station: {station_id}")
        return None
    
    def get_all_predictions(self, file_hash: str) -> List[Dict[str, Any]]:
        """파일별 모든 예측 결과 조회"""
        if self.db:
            try:
                results = self.db.get_all_predictions(file_hash)
                logger.info(f"Loaded {len(results)} predictions from database for file {file_hash}")
                return results
            except Exception as e:
                logger.error(f"Failed to get all predictions from database: {e}")
        
        # 파일에서 폴백
        return self._get_all_from_files(file_hash)
    
    def start_batch_processing(self, file_hash: str, total_stations: int) -> bool:
        """배치 처리 시작"""
        if self.db:
            return self.db.create_batch_progress(file_hash, total_stations)
        return True
    
    def update_batch_progress(self, file_hash: str, completed: int = None, 
                            failed: int = None, status: str = None) -> bool:
        """배치 처리 진행상황 업데이트"""
        if self.db:
            return self.db.update_batch_progress(file_hash, completed, failed, status)
        return True
    
    def get_batch_progress(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """배치 처리 진행상황 조회"""
        if self.db:
            return self.db.get_batch_progress(file_hash)
        
        # 파일 기반 폴백
        progress_file = self.file_storage_path / f"{file_hash}_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load progress from file: {e}")
        
        return None
    
    def _save_to_file(self, station_id: str, prediction_data: Dict[str, Any], 
                     file_hash: str = None) -> None:
        """파일에 예측 결과 저장"""
        filename = f"{file_hash}_{station_id}_prediction.json" if file_hash else f"{station_id}_prediction.json"
        file_path = self.file_storage_path / filename
        
        data = {
            "station_id": station_id,
            "file_hash": file_hash,
            "timestamp": datetime.now().isoformat(),
            "prediction": prediction_data
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_from_file(self, station_id: str, file_hash: str = None) -> Optional[Dict[str, Any]]:
        """파일에서 예측 결과 로드"""
        filename = f"{file_hash}_{station_id}_prediction.json" if file_hash else f"{station_id}_prediction.json"
        file_path = self.file_storage_path / filename
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('prediction', data)  # 호환성 유지
        
        return None
    
    def _get_all_from_files(self, file_hash: str) -> List[Dict[str, Any]]:
        """파일들에서 모든 예측 결과 조회"""
        results = []
        pattern = f"{file_hash}_*_prediction.json"
        
        for file_path in self.file_storage_path.glob(pattern):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    prediction_data = data.get('prediction', data)
                    prediction_data['station_id'] = data.get('station_id', 
                                                            file_path.stem.split('_')[1])
                    results.append(prediction_data)
            except Exception as e:
                logger.warning(f"Failed to load prediction from {file_path}: {e}")
        
        return results
    
    def cleanup_old_data(self, days_old: int = 30) -> Dict[str, int]:
        """오래된 데이터 정리"""
        results = {"database_cleaned": 0, "files_cleaned": 0}
        
        # 데이터베이스 정리
        if self.db:
            try:
                results["database_cleaned"] = self.db.cleanup_old_predictions(days_old)
            except Exception as e:
                logger.error(f"Database cleanup failed: {e}")
        
        # 파일 정리
        try:
            cutoff_date = datetime.now()
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)
            
            for file_path in self.file_storage_path.glob("*_prediction.json"):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    file_path.unlink()
                    results["files_cleaned"] += 1
                    
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")
        
        return results
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """저장소 통계 정보"""
        stats = {
            "database_enabled": self.db is not None,
            "file_backup_enabled": True,
            "total_prediction_files": len(list(self.file_storage_path.glob("*_prediction.json"))),
            "storage_path": str(self.base_path),
        }
        
        if self.db:
            try:
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM prediction_results")
                    stats["database_predictions"] = cursor.fetchone()[0]
                    
                    cursor = conn.execute("SELECT COUNT(*) FROM batch_progress")
                    stats["batch_processes"] = cursor.fetchone()[0]
            except Exception as e:
                logger.warning(f"Failed to get database stats: {e}")
                stats["database_predictions"] = "unknown"
                stats["batch_processes"] = "unknown"
        
        return stats