from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re

class ActionSelectCoffeeSize(Action):
    def name(self) -> Text:
        return "action_select_coffee_size"  # 액션의 이름을 정의하는 메서드

    # start 값이 가장 큰, 즉 사용자의 대화에서 가장 마지막에 오는 size 엔티티 값을 추출
    def extract_last_size(self, entities):
        # size 엔티티를 필터링하여 해당 엔티티들만 리스트로 만듦
        size_entities = [entity for entity in entities if entity["entity"] == "size"]
        # 필터링된 size 엔티티가 있을 경우
        if size_entities:
            # 'start' 값을 기준으로 가장 큰 엔티티를 찾고, 해당 엔티티의 'value' 값을 반환
            return max(size_entities, key=lambda x: x['start'])["value"]
        return None  # size 엔티티가 없을 경우 None 반환

    # 커피 사이즈를 변경하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            user_text = tracker.latest_message.get("text", "")

            if "사이즈 업" in user_text:
                raise KeyError("size up")
            
            order_manager = OrderManager()
            order_mapper =OrderMapper()     

            # 엔티티를 위치 순서로 정렬하고 매핑
            mapper = OrderMapper(entities, is_size_change=True)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 로그로 입력된 엔티티와 매핑된 데이터를 출력
            logging.warning(f"커피 사이즈 변경 입력 내용 텍스트: {user_text}")
            logging.warning(f"커피 사이즈 변경 입력 내용 엔티티: {entities}")
            logging.warning(f"커피 사이즈 변경 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            order_utils.raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 가장 마지막에 오는 size 엔티티 값을 new_size로 설정
            new_size = self.extract_last_size(entities)

            if new_size is None:
                dispatcher.utter_message(text="새로운 사이즈를 지정해주세요.")
                return []  # 새로운 사이즈가 지정되지 않으면 메서드를 종료

            # 현재 사이즈를 구분
            current_sizes = [entity["value"] for entity in entities if entity["entity"] == "size" and entity["value"] != new_size]
            current_size = current_sizes[-1] if current_sizes else "미디움"

            for i in range(len(drink_types)):
                drink = drink_types[i]  # 변경할 음료의 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 변경할 음료의 수량
                temperature = temperatures[i] if i < len(temperatures) else None  # 음료의 온도
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션

                # 로그로 변경할 음료의 정보 출력
                logging.warning(f"온도: {temperature}, 변경 대상 음료: {drink}, 수량: {quantity}, 현재 사이즈: {current_size}, 새로운 사이즈: {new_size}")

                try:
                    # 현재 주문된 음료를 기존 사이즈로 제거
                    order_manager.subtract_order(drink, quantity, temperature, current_size, additional_option)
                    # 새로운 사이즈로 주문 추가
                    order_manager.add_order(drink, quantity, temperature, new_size, additional_option)
                except ValueError as e:
                    # 오류 발생 시 사용자에게 메시지 전달
                    dispatcher.utter_message(text=str(e))
                    return []

            # 사이즈 변경 완료 메시지 생성 및 사용자에게 전달
            confirmation_message = f"사이즈가 변경되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text=f"사이즈 변경 중 오류가 발생했습니다: {str(e)}")
            return []
