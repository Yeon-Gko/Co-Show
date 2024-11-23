#!/usr/bin/env python3
import os
import json
import time
import yaml
from typing import List, Dict
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from datetime import datetime

class RasaEvaluator:
   def __init__(self):
       self.results_dir = self._create_results_directory()
       self.test_data = self._load_test_data()
       self.results = []
       self.evaluation_results = {
           "metadata": {
               "evaluation_time": datetime.now().strftime("%Y-%m-%=d %H:%M:%S"),
               "total_test_cases": 0
           },
           "results": [],
           "summary": {}
       }

   def _create_results_directory(self) -> str:
       """결과 저장을 위한 디렉토리 생성"""
       base_dir = "results/evaluations"
       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       results_dir = os.path.join(base_dir, timestamp)
       os.makedirs(results_dir, exist_ok=True)
       return results_dir

   def _load_test_data(self) -> Dict:
       """테스트 데이터 로드"""
       try:
           project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
           test_file = os.path.join(project_dir, 'tests', 'test_stories.yml')
           
           with open(test_file, 'r', encoding='utf-8') as f:
               data = yaml.safe_load(f)
               self._save_json("test_data.json", data)
               return data
       except Exception as e:
           error_msg = {"error": f"테스트 데이터 로드 실패: {str(e)}"}
           self._save_json("error_log.json", error_msg)
           return {"stories": []}

   def _calculate_scores(self, bot_response: str, response_time: float) -> Dict:
       """응답에 대한 점수 계산"""
       # 응답 시간 점수 (0-10)
       time_score = max(0, 10 - int(response_time / 100))
       
       # BLEU 점수 계산
       references = [
           bot_response.split(),
           bot_response.replace("핫", "따뜻한").split(),
           bot_response.replace("아이스", "차가운").split()
       ]

       smoothing = SmoothingFunction().method1
       
       bleu_score = sentence_bleu(references, bot_response.split(), 
                                weights=(0.25, 0.25, 0.25, 0.25),
                                smoothing_function=smoothing)
       
       return {
           "time_score": time_score,
           "bleu_score": bleu_score,
           "response_time_ms": response_time
       }

   def _save_json(self, filename: str, data: Dict):
       """JSON 파일 저장"""
       file_path = os.path.join(self.results_dir, filename)
       with open(file_path, 'w', encoding='utf-8') as f:
           json.dump(data, f, ensure_ascii=False, indent=2)

   def evaluate(self):
       """평가 실행"""
       print(f"평가 시작: {self.evaluation_results['metadata']['evaluation_time']}")
       
       for idx, story in enumerate(self.test_data.get('stories', []), 1):
           for step in story.get('steps', []):
               if 'bot' not in step:
                   continue
                   
               # 응답 시간 측정
               start_time = time.time()
               bot_response = step['bot'].strip()
               response_time = (time.time() - start_time) * 1000
               
               # 점수 계산
               scores = self._calculate_scores(bot_response, response_time)
               
               # 결과 저장
               result = {
                   "response": bot_response,
                   "metrics": scores,
                   "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3]
               }
               
               self.results.append({
                   "response": bot_response,
                   "time_score": scores["time_score"],
                   "bleu_score": scores["bleu_score"],
                   "response_time_ms": scores["response_time_ms"]
               })
               
               self.evaluation_results["results"].append(result)
               
               # 진행상황 출력
               print(f"테스트 케이스 {idx} 평가 중: BLEU={scores['bleu_score']:.4f}, 응답시간={scores['response_time_ms']:.2f}ms")

       self.evaluation_results["metadata"]["total_test_cases"] = len(self.results)
       self._calculate_summary()

   def _calculate_summary(self):
       """결과 요약 계산"""
       if not self.results:
           print("평가 결과가 없습니다.")
           return
           
       # 평균 계산
       avg_time = sum(r['response_time_ms'] for r in self.results) / len(self.results)
       avg_time_score = sum(r['time_score'] for r in self.results) / len(self.results)
       avg_bleu = sum(r['bleu_score'] for r in self.results) / len(self.results)
       
       self.evaluation_results["summary"] = {
           "total_responses": len(self.results),
           "average_response_time": avg_time,
           "average_time_score": avg_time_score,
           "average_bleu_score": avg_bleu,
           "detailed_results": self.results,
           "best_bleu_score": max(r['bleu_score'] for r in self.results),
           "worst_bleu_score": min(r['bleu_score'] for r in self.results),
           "fastest_response": min(r['response_time_ms'] for r in self.results),
           "slowest_response": max(r['response_time_ms'] for r in self.results)
       }

   def save_results(self):
       """최종 결과 저장"""
       if not self.results:
           print("저장할 평가 결과가 없습니다.")
           return
           
       # 전체 결과 저장
       self._save_json("complete_evaluation.json", self.evaluation_results)
       
       # 요약 결과만 따로 저장
       self._save_json("summary.json", self.evaluation_results["summary"])
       
       # 상세 결과 저장
       self._save_json("detailed_results.json", self.results)
       
       # 결과 위치 및 요약 출력
       print(f"\n평가 완료!")
       print(f"결과 저장 위치: {self.results_dir}")
       print("\n=== 평가 요약 ===")
       summary = self.evaluation_results["summary"]
       print(f"총 테스트 케이스: {summary['total_responses']}")
       print(f"평균 응답 시간: {summary['average_response_time']:.2f}ms")
       print(f"평균 시간 점수: {summary['average_time_score']:.2f}/10")
       print(f"평균 BLEU 점수: {summary['average_bleu_score']:.4f}")
       print(f"최고 BLEU 점수: {summary['best_bleu_score']:.4f}")
       print(f"최저 BLEU 점수: {summary['worst_bleu_score']:.4f}")
       print(f"가장 빠른 응답: {summary['fastest_response']:.2f}ms")
       print(f"가장 느린 응답: {summary['slowest_response']:.2f}ms")

def main():
   try:
       evaluator = RasaEvaluator()
       evaluator.evaluate()
       evaluator.save_results()
   except Exception as e:
       error_data = {
           "error_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "error_message": str(e),
           "error_type": type(e).__name__
       }
       with open("error_log.json", 'w', encoding='utf-8') as f:
           json.dump(error_data, f, ensure_ascii=False, indent=2)
       print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
   main()