from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re

class ActionOrderConfirmation(Action):

    logging.warning(f"----------------<class 'rasa_sdk.interfaces.Action'>-----------------")
    logging.warning(f"주문 Action 정보: {Action}")
    logging.warning(f"---------------------------------------------------------------------")

    def name(self) -> Text:
        return "action_order_confirmation"

    #학습 된데이터를 받는곳으로 추정.
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # # 현재 주문 정보 초기화(주문을 하는데 이전 주문 정보가 남아있으면 안됨)
            # order_manager.clear_order()
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            user_text = tracker.latest_message.get("text", "")
            order_manager = OrderManager() 

            if "사이즈 업" in user_text:
                raise KeyError("size up")

            # 엔티티를 위치 순서로 정렬
            mapper = OrderMapper(entities)
            # mapper.get_mapped_data()를 이용해 temperatures, drink_types, sizes, quantities, additional_options 값 받아오기
            '''
            get_mapped_data(self): 메소드 기능.
                    temperatures = [drink["temperature"] for drink in self.drinks]
                    drink_types = [drink["drink_type"] for drink in self.drinks]
                    sizes = [drink["size"] for drink in self.drinks]
                    quantities = [drink["quantity"] for drink in self.drinks]
                    additional_options = [", ".join(drink["additional_options"]) for drink in self.drinks]
                    return temperatures, drink_types, sizes, quantities, additional_options

            '''
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            logging.warning(f"주문 엔티티: {entities}")
            logging.warning(f"온도, 커피, 사이즈, 잔 수, 옵션: {temperatures} {drink_types} {sizes} {quantities} {additional_options}")

            # 고정된 온도 음료의 온도 확인
            hot_drinks = ["허브티"]
            ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

            for i in range(len(drink_types)):
                # drink_types[i] in hot_drinks, temperatures[i] != "핫"(즉, 핫 음료 목록에 포함되지만 온도가 "핫"이 아닌 경우에만)
                if drink_types[i] in hot_drinks and temperatures[i] != "핫":
                    raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
                if drink_types[i] in ice_only_drinks and temperatures[i] != "아이스":
                    raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")

            order_utils.raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            if drink_types and quantities:
                for i in range(len(drink_types)):
                    order_manager.add_order(drink_types[i], quantities[i], temperatures[i], sizes[i], additional_options[i])
            
            # 메세지 생성
            confirmation_message = f"주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            # 출력
            dispatcher.utter_message(text=confirmation_message)

        except ValueError as e:
            dispatcher.utter_message(text=str(e))
        except Exception as e:
            dispatcher.utter_message(text=f"주문 접수 중 오류가 발생했습니다: {str(e)}")
        return []
    