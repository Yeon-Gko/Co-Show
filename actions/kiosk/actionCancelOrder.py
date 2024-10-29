from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re


class ActionCancelOrder(Action):
    def name(self) -> Text:
        return "action_cancel_order"

    # 주문을 취소하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            order_manager = OrderManager()
            order_mapper =OrderMapper()
            # 현재 주문된 음료 목록 가져오기
            current_orders = order_manager.get_orders()

            if not current_orders:
                # 취소할 주문이 없는 경우
                dispatcher.utter_message(text="취소할 주문이 없습니다.")
                return []

            # 주문 취소 메시지 생성
            cancellation_message = f"모든 주문이 취소되었습니다. 취소된 음료는 {order_manager.get_order_summary()}입니다. 새로운 주문을 원하시면 말씀해주세요."
            order_manager.clear_order()
            
            dispatcher.utter_message(text=cancellation_message)
            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_cancel_order")
            dispatcher.utter_message(text="주문을 취소하는 중에 오류가 발생했습니다. 다시 시도해주세요.")
            return []
