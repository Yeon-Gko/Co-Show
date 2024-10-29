from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import logging
import re

class ActionTakeOut(Action):
    def name(self) -> Text:
        return "action_takeout"

    # 주문을 완료하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:          
            # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]

            # 테이크 엔티티 확인
            logging.warning(f"테이크아웃 엔티티: {entities}")

            # x 값을 기준으로 엔티티 정렬
            sorted_entities = sorted(entities, key=lambda e: e.get("x", 0))

            # 'take' 엔티티 필터링
            take_entities = [entity for entity in sorted_entities if entity.get("entity") == "take"]

            if take_entities:
                if len(take_entities) == 1:
                    # 'take' 엔티티가 하나일 경우 그 값을 사용
                    last_take_value = take_entities[0].get("value")
                else:
                    # 'take' 엔티티가 여러 개일 경우 가장 마지막의 값 사용
                    last_take_value = take_entities[-1].get("value")

                # take 엔티티 표준화
                takeout = standardize_take(last_take_value)

                # 최종 주문 메시지 생성
                final_message = f"{takeout} 주문이 완료되었습니다. 결제는 하단의 카드리더기로 결제해 주시기 바랍니다. 감사합니다."
            # 메시지 출력
            dispatcher.utter_message(text=final_message)
            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_order_finish")
            dispatcher.utter_message(text="결제 중 오류가 발생했습니다. 다시 시도해주세요.")
            return []
