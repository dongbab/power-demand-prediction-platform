import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class PredictionDatabase:
    def __init__(self, db_path: str = "data/predictions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prediction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id TEXT NOT NULL,
                    file_hash TEXT,
                    prediction_data TEXT NOT NULL,  -- JSON 형태로 저장
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(station_id, file_hash)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT UNIQUE NOT NULL,
                    total_stations INTEGER NOT NULL,
                    completed_stations INTEGER DEFAULT 0,
                    failed_stations INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processing',  -- processing, completed, failed
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_station_file ON prediction_results(station_id, file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON batch_progress(file_hash)")
            
            conn.commit()
    
    def save_prediction(self, station_id: str, prediction_data: Dict[str, Any], 
                       file_hash: str = None) -> bool:
        """예측 결과 저장"""
        try:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO prediction_results 
                    (station_id, file_hash, prediction_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (station_id, file_hash, json.dumps(prediction_data), now, now))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save prediction for {station_id}: {e}")
            return False
    
    def load_prediction(self, station_id: str, file_hash: str = None) -> Optional[Dict[str, Any]]:
        """저장된 예측 결과 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT prediction_data, created_at FROM prediction_results 
                    WHERE station_id = ? AND (file_hash = ? OR file_hash IS NULL)
                    ORDER BY updated_at DESC LIMIT 1
                """, (station_id, file_hash))
                
                row = cursor.fetchone()
                if row:
                    data = json.loads(row['prediction_data'])
                    data['_cached_at'] = row['created_at']
                    return data
            return None
        except Exception as e:
            logger.error(f"Failed to load prediction for {station_id}: {e}")
            return None
    
    def get_all_predictions(self, file_hash: str = None) -> List[Dict[str, Any]]:
        """파일별 모든 예측 결과 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT station_id, prediction_data, created_at FROM prediction_results 
                    WHERE file_hash = ?
                    ORDER BY station_id
                """, (file_hash,))
                
                results = []
                for row in cursor.fetchall():
                    data = json.loads(row['prediction_data'])
                    data['station_id'] = row['station_id']
                    data['_cached_at'] = row['created_at']
                    results.append(data)
                
                return results
        except Exception as e:
            logger.error(f"Failed to get predictions for file {file_hash}: {e}")
            return []
    
    def create_batch_progress(self, file_hash: str, total_stations: int) -> bool:
        """배치 처리 진행상황 생성"""
        try:
            now = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO batch_progress 
                    (file_hash, total_stations, started_at, status)
                    VALUES (?, ?, ?, 'processing')
                """, (file_hash, total_stations, now))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to create batch progress for {file_hash}: {e}")
            return False
    
    def update_batch_progress(self, file_hash: str, completed: int = None, 
                            failed: int = None, status: str = None) -> bool:
        """배치 처리 진행상황 업데이트"""
        try:
            updates = []
            params = []
            
            if completed is not None:
                updates.append("completed_stations = ?")
                params.append(completed)
            
            if failed is not None:
                updates.append("failed_stations = ?")
                params.append(failed)
                
            if status is not None:
                updates.append("status = ?")
                params.append(status)
                if status == 'completed':
                    updates.append("completed_at = ?")
                    params.append(datetime.now().isoformat())
            
            if updates:
                params.append(file_hash)
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(f"""
                        UPDATE batch_progress 
                        SET {', '.join(updates)}
                        WHERE file_hash = ?
                    """, params)
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update batch progress for {file_hash}: {e}")
            return False
    
    def get_batch_progress(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """배치 처리 진행상황 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM batch_progress WHERE file_hash = ?
                """, (file_hash,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get batch progress for {file_hash}: {e}")
            return None
    
    def cleanup_old_predictions(self, days_old: int = 30) -> int:
        """오래된 예측 결과 정리"""
        try:
            cutoff_date = datetime.now()
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM prediction_results 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old prediction records")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old predictions: {e}")
            return 0