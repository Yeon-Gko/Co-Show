from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re


class ActionAddSubtract(Action):
    def name(self) -> Text:
        return "action_add_subtract"
    
    def __init__(self):
        self.order_manager = OrderManager()
        self.order_mapper = OrderMapper()
        

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            
            # 최근 사용자 메시지에서 엔티티 가져오기
            entities = sorted([entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"], key=lambda x: x['start'])

            add_entities = []
            subtract_entities = []

            current_order = self._initialize_order()
            # 추가하는 부분과 제거하는 부분을 나누기 위한 값을 저장.
            current_action = None

            logging.warning(f"주문 다중처리 엔티티: {entities}")
            
            # 엔티티를 인덱스 값과 같이 가장 처음부터 순서대로 반복합니다.
            for i, entity in enumerate(entities):
                # 현재 엔티티의 entity가 'add'면서 리스트의 첫 번째 엔티티가 'add'거나 'add'엔티티가 'additional_options' 뒤에 있지 않으면(뒤에 있으면 추가옵션 꺼)
                if entity['entity'] == 'add' and (i == 0 or entities[i-1]['entity'] != 'additional_options'):
                    current_action = 'add' # 추가하는 부분
                    if current_order['drink_type']:
                        add_entities.append(current_order)
                    current_order = self._initialize_order() # 새로운 주문을 시작하기 위해 현재 주문을 초기화
                    logging.warning(f"다중처리 추가 : {add_entities}")
                elif entity['entity'] == 'subtract':
                    current_action = 'subtract' # 제거하는 부분
                    if current_order['drink_type']:
                        subtract_entities.append(current_order)
                    current_order = self._initialize_order() # 새로운 주문을 시작하기 위해 현재 주문을 초기화
                    logging.warning(f"다중처리 제거 : {subtract_entities}")
                else:
                    self._map_entity_to_order(entity, current_order)

            # 누락 주문 처리(다중처리 인텐트가 인식되서 기능은 실행이 되었는데 채팅이 ~는 추가해주시고 나 ~는 빼주시고 에서 말이 끊기거나 했을 때 실행되도록)
            if current_order['drink_type']:
                if current_action == 'add':
                    add_entities.append(current_order)
                elif current_action == 'subtract':
                    subtract_entities.append(current_order)

            # 온도의 기본값을 매핑
            self._set_default_temperature(add_entities)
            self._set_default_temperature(subtract_entities)

            # 매핑된 데이터 출력
            logging.warning(f"추가 엔티티: {add_entities}, 제거 엔티티: {subtract_entities}")

            # 추가 엔티티가 있는 경우 처리
            for order in add_entities:
                self._process_add(order)

            # 제거 엔티티가 있는 경우 처리
            for order in subtract_entities:
                self._process_subtract(order, dispatcher)

            # 정리된 최종 주문 리스트를 생성
            confirmation_message = f"주문이 수정되었습니다. 현재 주문은 {self.order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)
            return []
        except Exception as e:
            logging.exception("Exception occurred in action_add_subtract")
            dispatcher.utter_message(text=str(e))
            return []

    # 음료의 종류와 온도를 제외한 기본값 메서드
    def _initialize_order(self):
        return {
            "temperature": None,
            "drink_type": None,
            "size": "미디움",
            "quantity": 1,
            "additional_options": []
        }

    # 음료 매핑 메서드
    def _map_entity_to_order(self, entity, order):
        if entity['entity'] == 'drink_type':
            # 사용자 정의 음료 종류 설정
            if entity['value'] in ["아아", "아 아", "아", "아가"]:
                order['drink_type'] = "아메리카노"
                order['temperature'] = "아이스"
            elif entity['value'] in ["뜨아", "뜨 아", "뜨아아", "또", "응아", "쁘허", "뚜아"]:
                order['drink_type'] = "아메리카노"
                order['temperature'] = "핫"
            else:
                order['drink_type'] = order_utils.standardize_drink_name(entity['value'])
        elif entity['entity'] == 'quantity':
            quantity = entity['value']
            order['quantity'] = int(quantity) if quantity.isdigit() else order_utils.korean_to_number(quantity)
        elif entity['entity'] == 'temperature':
            if order['temperature'] is None:
                order['temperature'] = order_utils.standardize_temperature(entity['value'])
        elif entity['entity'] == 'size':
            order['size'] = order_utils.standardize_size(entity['value'])
        elif entity['entity'] == 'additional_options':
            order['additional_options'].append(order_utils.standardize_option(entity['value']))

    # 온도 기본값 성정 메서드
    def _set_default_temperature(self, orders):
        hot_drinks = ["허브티"]
        ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

        for order in orders:
            if order['temperature'] is None:
                if order['drink_type'] in hot_drinks:
                    order['temperature'] = "핫"
                elif order['drink_type'] in ice_only_drinks:
                    order['temperature'] = "아이스"
                else:
                    order['temperature'] = "핫"
            else:
                # 온도가 이미 설정되었고 온도가 고정된 음료의 온도가 잘못되었을 때
                if order['drink_type'] in hot_drinks and order['temperature'] != "핫":
                    raise ValueError(f"{order['drink_type']}는(은) 온도가 핫으로 고정된 음료입니다! 다시 주문해 주세요.")
                elif order['drink_type'] in ice_only_drinks and order['temperature'] != "아이스":
                    raise ValueError(f"{order['drink_type']}는(은) 온도가 아이스로 고정된 음료입니다! 다시 주문해 주세요.")

    # 음료 제거 메서드
    def _process_subtract(self, order, dispatcher):
        try:
            if order['drink_type'] in self.order_manager.get_orders():
                self.order_manager.subtract_order(order['drink_type'], order['quantity'], order['temperature'], order['size'], ", ".join(order['additional_options']))
            else:
                raise ValueError(f"{order['drink_type']}은(는) 등록되지 않은 커피입니다! 다시 주문해주세요.")
        except ValueError as e:
            dispatcher.utter_message(text=str(e))

    # 음료 추가 메서드
    def _process_add(self, order):
        self.order_manager.add_order(order['drink_type'], order['quantity'], order['temperature'], order['size'], ", ".join(order['additional_options']))
        