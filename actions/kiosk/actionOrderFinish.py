from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re


class ActionOrderFinish(Action):
    def name(self) -> Text:
        return "action_order_finish"

    # 주문을 완료하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            order_manager = OrderManager()
            order_mapper =OrderMapper()

            # 주문 데이터 확인
            if not order_manager.get_orders():
                # 주문이 없는 경우
                dispatcher.utter_message(text="장바구니에 주문이 없습니다. 다시 주문해 주세요.")
                return []
            
            # 최종 주문 메시지 생성
            final_message = f"주문하신 음료는 {order_manager.get_order_summary()}입니다."
            dispatcher.utter_message(text=final_message)
            dispatcher.utter_message(response="utter_takeout")

            # 주문 완료 후 저장된 커피 데이터 초기화
            order_manager.clear_order()

            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_order_finish")
            dispatcher.utter_message(text="결제 중 오류가 발생했습니다. 다시 시도해주세요.")
            return []
