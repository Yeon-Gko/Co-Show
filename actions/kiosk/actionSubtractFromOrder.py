from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import logging
import re

class ActionSubtractFromOrder(Action):

    def name(self) -> Text:
        # 액션의 이름을 반환하는 메소드
        return "action_subtract_from_order"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 DIETClassifier가 아닌 엔티티들을 가져옴
            subtract_entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            # OrderMapper를 사용하여 엔티티들을 매핑
            mapper = OrderMapper(subtract_entities)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            logging.warning(f"사용자 주문 제거 입력 내용: {subtract_entities}")
            logging.warning(f"사용자 주문 제거 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            order_manager = OrderManager()
            order_mapper =OrderMapper()            
        
            order_manager.raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증(아이스 들어간 음료 다 취소. 가 드링크 타입이 없는데 왜 에러가 안뜨지?)

            # 매핑된 데이터를 순회하면서 주문 제거
            for i in range(len(drink_types)):
                drink = drink_types[i]  # 음료 종류
                quantity = quantities[i]  # 잔 수
                size = sizes[i] if i < len(sizes) else None  # 사이즈
                temperature = temperatures[i] if i < len(temperatures) else None  # 온도
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션
                
                try:
                    # 주문에 해당 음료가 있는지 확인하고 제거
                    if drink in order_manager.get_orders():
                        logging.warning(f"{temperature, drink, size, quantity, additional_option}")
                        order_manager.subtract_order(drink, quantity, temperature, size, additional_option)
                    else:
                        raise ValueError(f"{drink}은(는) 등록되지 않은 커피입니다! 다시 주문해주세요.")
                except ValueError as e:
                    dispatcher.utter_message(text=str(e))

            # 남아있는 주문이 있는지 확인하고 사용자에게 메시지 전송
            if order_manager.get_orders():
                confirmation_message = f"주문에서 음료가 제거되었습니다. 현재 주문은 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
                dispatcher.utter_message(text=confirmation_message)
            else:
                dispatcher.utter_message(text="모든 음료가 주문에서 제거되었습니다.")

            return []
        except ValueError as e:
            dispatcher.utter_message(text=str(e))
        except Exception as e:
            # 오류 발생 시 사용자에게 오류 메시지 전송
            dispatcher.utter_message(text=f"주문 제거 중 오류가 발생했습니다: {str(e)}")
            return []