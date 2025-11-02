"""
RAG 고도화 전/후 비교 테스트
"""
import json
import sys
import os
import time
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

from commitary_backend.app import create_app

# 테스트 설정
TEST_REPO_ID = 1061647946
TEST_BRANCH = "main"
TEST_COMMITARY_ID = 1
TEST_DATE_STR = "2025-09-30"


def delete_existing_insight(app, test_date_str):
    """기존 인사이트 삭제"""
    print(f"\n🗑️ 기존 인사이트 삭제 중 (날짜: {test_date_str})...")
    
    with app.app_context():
        from commitary_backend.commitaryUtils.dbConnectionDecorator import get_db_conn
        
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM insight_item 
                    WHERE daily_insight_id IN (
                        SELECT daily_insight_id 
                        FROM daily_insight 
                        WHERE date = %s AND repo_id = %s
                    )
                """, (test_date_str, TEST_REPO_ID))
                
                deleted_items = cur.rowcount
                
                cur.execute("""
                    DELETE FROM daily_insight 
                    WHERE date = %s AND repo_id = %s
                """, (test_date_str, TEST_REPO_ID))
                
                deleted_insights = cur.rowcount
                
                conn.commit()
                print(f"  ✅ 삭제 완료: {deleted_insights}개 인사이트, {deleted_items}개 아이템")
        except Exception as e:
            conn.rollback()
            print(f"  ❌ 삭제 실패: {e}")


def create_insight_with_version(app, version="OLD"):
    """특정 버전으로 인사이트 생성 + 메트릭 수집"""
    print(f"\n📊 {version} 버전으로 인사이트 생성 중...")
    
    metrics = {
        "total_time": 0,
        "embedding_tokens": 0,
        "embedding_calls": 0,
        "llm_tokens": 0,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0
    }
    
    with app.app_context():
        if version == "OLD":
            from commitary_backend.services.insightService.OLD.InsightServiceObject_OLD import InsightService
        else:
            from commitary_backend.services.insightService.InsightServiceObject import InsightService
        
        insight_service = InsightService()
        
        import logging
        from io import StringIO
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        app.logger.addHandler(handler)
        
        try:
            test_datetime = datetime.strptime(TEST_DATE_STR, "%Y-%m-%d")
            test_datetime = test_datetime.replace(hour=12, minute=0, second=0, tzinfo=timezone.utc)
            
            print(f"  레포: Seongbong-Ha/dotodo_backend (ID: {TEST_REPO_ID})")
            print(f"  날짜: {TEST_DATE_STR}")
            print(f"  브랜치: {TEST_BRANCH}")
            
            start_time = time.time()
            
            status = insight_service.createDailyInsight(
                commitary_id=TEST_COMMITARY_ID,
                repo_id=TEST_REPO_ID,
                start_datetime=test_datetime,
                branch=TEST_BRANCH,
                user_token=GITHUB_TOKEN
            )
            
            metrics["total_time"] = time.time() - start_time
            
            log_contents = log_capture.getvalue()
            
            # 임베딩 토큰 추출
            embedding_pattern = r"Token count \(estimated\): (\d+)"
            embedding_matches = re.findall(embedding_pattern, log_contents)
            if embedding_matches:
                metrics["embedding_tokens"] = sum(int(x) for x in embedding_matches)
                metrics["embedding_calls"] = len(embedding_matches)
            
            # LLM 토큰 추출
            llm_pattern = r"Total Tokens: (\d+).*?Prompt Tokens: (\d+).*?Completion Tokens: (\d+)"
            llm_matches = re.findall(llm_pattern, log_contents, re.DOTALL)
            if llm_matches:
                total, prompt, completion = llm_matches[-1]
                metrics["llm_tokens"] = int(total)
                metrics["llm_prompt_tokens"] = int(prompt)
                metrics["llm_completion_tokens"] = int(completion)
            
            print(f"  생성 상태: {status}")
            
            status_messages = {
                0: "✅ 인사이트 생성 성공",
                1: "ℹ️ 이미 존재하는 인사이트",
                -1: "⚠️ 활동 없음",
                2: "❌ 생성 실패"
            }
            print(f"  {status_messages.get(status, '❓ 알 수 없는 상태')}")
            
            print(f"\n⏱️ 성능 메트릭:")
            print(f"  전체 시간: {metrics['total_time']:.2f}초")
            print(f"  임베딩 토큰: {metrics['embedding_tokens']:,}개 ({metrics['embedding_calls']}회)")
            print(f"  LLM 토큰: {metrics['llm_tokens']:,}개 (프롬프트: {metrics['llm_prompt_tokens']:,}, 응답: {metrics['llm_completion_tokens']:,})")
            
            if status not in [0, 1]:
                return {
                    "status": "error",
                    "message": f"인사이트 생성 실패 (status: {status})",
                    "metrics": metrics
                }
            
            start_dt = test_datetime - timedelta(days=1)
            end_dt = test_datetime + timedelta(days=1)
            
            insights_dto = insight_service.getInsights(
                commitary_id=TEST_COMMITARY_ID,
                repo_id=TEST_REPO_ID,
                start_datetime=start_dt,
                end_datetime=end_dt
            )
            
            for insight in insights_dto.insights:
                insight_date_str = insight.date_of_insight.strftime("%Y-%m-%d")
                if insight_date_str == TEST_DATE_STR and insight.activity:
                    for item in insight.items:
                        if item.branch_name == TEST_BRANCH:
                            return {
                                "status": "success",
                                "date": TEST_DATE_STR,
                                "branch": TEST_BRANCH,
                                "insight": item.insight,
                                "length": len(item.insight),
                                "metrics": metrics
                            }
            
            return {
                "status": "not_found",
                "message": "인사이트를 찾을 수 없습니다",
                "metrics": metrics
            }
        
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": str(e),
                "metrics": metrics
            }
        
        finally:
            app.logger.removeHandler(handler)


def analyze_insights(old_result, new_result):
    """인사이트 분석 및 비교"""
    print("\n" + "="*80)
    print("📊 인사이트 비교 분석")
    print("="*80)
    
    if old_result["status"] != "success":
        print(f"\n⚠️ 고도화 전 인사이트 실패: {old_result.get('message', 'Unknown')}")
    
    if new_result["status"] != "success":
        print(f"\n⚠️ 고도화 후 인사이트 실패: {new_result.get('message', 'Unknown')}")
    
    if old_result["status"] != "success" or new_result["status"] != "success":
        return
    
    print(f"\n📏 인사이트 길이 비교")
    print(f"  고도화 전: {old_result['length']:,} 자")
    print(f"  고도화 후: {new_result['length']:,} 자")
    diff = new_result['length'] - old_result['length']
    percent = (diff / old_result['length'] * 100) if old_result['length'] > 0 else 0
    print(f"  차이: {diff:+,} 자 ({percent:+.1f}%)")
    
    print(f"\n📋 구조 분석")
    
    old_has_summary = '변경사항 요약' in old_result['insight']
    new_has_summary = '변경사항 요약' in new_result['insight']
    
    old_has_details = '주요 변경' in old_result['insight']
    new_has_details = '주요 변경' in new_result['insight']
    
    old_has_analysis = '기술적 분석' in old_result['insight']
    new_has_analysis = '기술적 분석' in new_result['insight']
    
    print(f"  변경사항 요약: 고도화 전 {'✅' if old_has_summary else '❌'} | 고도화 후 {'✅' if new_has_summary else '❌'}")
    print(f"  주요 변경 내역: 고도화 전 {'✅' if old_has_details else '❌'} | 고도화 후 {'✅' if new_has_details else '❌'}")
    print(f"  기술적 분석: 고도화 전 {'✅' if old_has_analysis else '❌'} | 고도화 후 {'✅' if new_has_analysis else '❌'}")
    
    print(f"\n" + "="*80)
    print("📄 고도화 전 인사이트")
    print("="*80)
    print(old_result['insight'])
    
    print(f"\n" + "="*80)
    print("📄 고도화 후 인사이트")
    print("="*80)
    print(new_result['insight'])
    
    comparison = {
        "test_info": {
            "repository": "Seongbong-Ha/dotodo_backend",
            "repo_id": TEST_REPO_ID,
            "test_date": TEST_DATE_STR,
            "branch": TEST_BRANCH,
            "test_time": datetime.now().isoformat()
        },
        "before_optimization": {
            "method": "고도화 전",
            "config": {
                "chunking": "RecursiveCharacterTextSplitter (언어 구분 없음)",
                "chunk_size": 1000,
                "chunk_overlap": 150,
                "retrieval": "단순 유사도 검색",
                "retrieval_count": 3
            },
            "result": {
                "length": old_result['length'],
                "has_summary": old_has_summary,
                "has_details": old_has_details,
                "has_analysis": old_has_analysis,
                "insight": old_result['insight']
            },
            "performance": {
                "latency_seconds": round(old_result.get('metrics', {}).get('total_time', 0), 2),
                "embedding_tokens": old_result.get('metrics', {}).get('embedding_tokens', 0),
                "embedding_calls": old_result.get('metrics', {}).get('embedding_calls', 0),
                "llm_tokens": {
                    "total": old_result.get('metrics', {}).get('llm_tokens', 0),
                    "prompt": old_result.get('metrics', {}).get('llm_prompt_tokens', 0),
                    "completion": old_result.get('metrics', {}).get('llm_completion_tokens', 0)
                }
            }
        },
        "after_optimization": {
            "method": "고도화 후",
            "config": {
                "chunking": "언어별 RecursiveCharacterTextSplitter",
                "chunk_size": 1500,
                "chunk_overlap": 200,
                "retrieval": "파일 기반 필터링 (2-stage)",
                "retrieval_count": "3 (changed) + 2 (other) = 5"
            },
            "result": {
                "length": new_result['length'],
                "has_summary": new_has_summary,
                "has_details": new_has_details,
                "has_analysis": new_has_analysis,
                "insight": new_result['insight']
            },
            "performance": {
                "latency_seconds": round(new_result.get('metrics', {}).get('total_time', 0), 2),
                "embedding_tokens": new_result.get('metrics', {}).get('embedding_tokens', 0),
                "embedding_calls": new_result.get('metrics', {}).get('embedding_calls', 0),
                "llm_tokens": {
                    "total": new_result.get('metrics', {}).get('llm_tokens', 0),
                    "prompt": new_result.get('metrics', {}).get('llm_prompt_tokens', 0),
                    "completion": new_result.get('metrics', {}).get('llm_completion_tokens', 0)
                }
            }
        },
        "comparison": {
            "length_diff": diff,
            "length_diff_percent": round(percent, 2)
        }
    }
    
    if "metrics" in old_result and "metrics" in new_result:
        old_m = old_result["metrics"]
        new_m = new_result["metrics"]
        
        time_diff = new_m['total_time'] - old_m['total_time']
        time_pct = (time_diff / old_m['total_time'] * 100) if old_m['total_time'] > 0 else 0
        
        emb_diff = new_m['embedding_tokens'] - old_m['embedding_tokens']
        emb_pct = (emb_diff / old_m['embedding_tokens'] * 100) if old_m['embedding_tokens'] > 0 else 0
        
        llm_diff = new_m['llm_tokens'] - old_m['llm_tokens']
        llm_pct = (llm_diff / old_m['llm_tokens'] * 100) if old_m['llm_tokens'] > 0 else 0
        
        old_cost = (
            (old_m['embedding_tokens'] / 1000) * 0.0001 +
            (old_m['llm_prompt_tokens'] / 1000) * 0.03 +
            (old_m['llm_completion_tokens'] / 1000) * 0.06
        )
        
        new_cost = (
            (new_m['embedding_tokens'] / 1000) * 0.0001 +
            (new_m['llm_prompt_tokens'] / 1000) * 0.03 +
            (new_m['llm_completion_tokens'] / 1000) * 0.06
        )
        
        cost_diff = new_cost - old_cost
        cost_pct = (cost_diff / old_cost * 100) if old_cost > 0 else 0
        
        comparison["comparison"]["performance"] = {
            "latency_diff_seconds": round(time_diff, 2),
            "latency_diff_percent": round(time_pct, 2),
            "embedding_tokens_diff": emb_diff,
            "embedding_tokens_diff_percent": round(emb_pct, 2),
            "llm_tokens_diff": llm_diff,
            "llm_tokens_diff_percent": round(llm_pct, 2),
            "cost_diff_usd": round(cost_diff, 4),
            "cost_diff_percent": round(cost_pct, 2),
            "cost_before_usd": round(old_cost, 4),
            "cost_after_usd": round(new_cost, 4)
        }
    
    output_file = "insight_comparison_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 상세 비교 결과가 '{output_file}'에 저장되었습니다.")

def delete_vector_snapshots(test_date_str, repo_id):
    """벡터 스냅샷 삭제"""
    print(f"\n🗑️ 벡터 스냅샷 삭제 중...")
    
    import psycopg2
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    conn = psycopg2.connect(DATABASE_URL)
    try:
        # 해당 주의 월요일 계산
        test_date = datetime.strptime(test_date_str, "%Y-%m-%d").date()
        monday_date = test_date - timedelta(days=test_date.weekday())
        snapshot_week_id = monday_date.isoformat()
        
        with conn.cursor() as cur:
            # OLD 컬렉션에서 삭제
            cur.execute("""
                DELETE FROM langchain_pg_embedding
                WHERE cmetadata->>'repo_id' = %s
                AND cmetadata->>'snapshot_week_id' = %s
                AND cmetadata->>'collection_name' = 'codebase_snapshots_OLD'
            """, (str(repo_id), snapshot_week_id))
            
            deleted_old = cur.rowcount
            
            # NEW 컬렉션에서 삭제
            cur.execute("""
                DELETE FROM langchain_pg_embedding
                WHERE cmetadata->>'repo_id' = %s
                AND cmetadata->>'snapshot_week_id' = %s
                AND cmetadata->>'collection_name' = 'codebase_snapshots_NEW'
            """, (str(repo_id), snapshot_week_id))
            
            deleted_new = cur.rowcount
            
            conn.commit()
            print(f"  ✅ 삭제 완료: OLD {deleted_old:,}개, NEW {deleted_new:,}개")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ 삭제 실패: {e}")
    finally:
        conn.close()


def main():
    print("\n" + "="*80)
    print("RAG 시스템 고도화 전/후 비교 테스트")
    print("="*80)
    print(f"\n테스트 대상:")
    print(f"  레포지토리: Seongbong-Ha/dotodo_backend")
    print(f"  날짜: {TEST_DATE_STR}")
    print(f"  브랜치: {TEST_BRANCH}")
    
    app = create_app()

    delete_vector_snapshots(TEST_DATE_STR, TEST_REPO_ID)
    
    delete_existing_insight(app, TEST_DATE_STR)
    
    old_result = create_insight_with_version(app, "OLD")
    
    print("\n🗑️ OLD 인사이트 삭제하고 NEW 준비...")
    delete_existing_insight(app, TEST_DATE_STR)
    
    new_result = create_insight_with_version(app, "NEW")
    
    analyze_insights(old_result, new_result)
    
    print("\n✅ 비교 테스트 완료!")


if __name__ == "__main__":
    if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_PERSONAL_ACCESS_TOKEN":
        print("ERROR: GITHUB_TOKEN이 설정되지 않았습니다.")
    else:
        main()