from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re

class ActionSelectCoffeeTemperature(Action):
    def name(self) -> Text:
        return "action_select_coffee_temperature"  # 액션의 이름을 정의하는 메서드

    # 가장 마지막에 오는 temperature 엔티티 값을 추출하고 변환
    def extract_last_temperature(self, entities):
        # temperature 엔티티를 필터링하여 해당 엔티티들만 리스트로 만듦
        temperature_entities = [entity for entity in entities if entity["entity"] == "temperature"]
        if temperature_entities:
            last_temp = max(temperature_entities, key=lambda x: x['start'])["value"]
            # '차갑게', '시원하게', '뜨겁게', '따뜻하게'를 각각 '아이스'와 '핫'으로 변환
            if last_temp in ["차갑게", "시원하게", "차가운", "시원한"]:
                return "아이스"
            elif last_temp in ["뜨겁게", "따뜻하게", "뜨거운", "따뜻한", "뜨뜻한", "따듯한"]:
                return "핫"
            return order_utils.standardize_temperature(last_temp)
        return None  # temperature 엔티티가 없을 경우 None 반환

    # 커피 온도를 변경하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            order_manager = OrderManager()
            order_mapper =OrderMapper()     

            # 엔티티를 위치 순서로 정렬하고 매핑
            mapper = OrderMapper(entities, is_temperature_change=True)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 로그로 입력된 엔티티와 매핑된 데이터를 출력
            logging.warning(f"커피 온도 변경 입력 내용: {entities}")
            logging.warning(f"커피 온도 변경 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            # 고정된 온도 음료의 온도 확인
            hot_drinks = ["허브티"]
            ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

            order_utils.raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 가장 마지막에 오는 temperature 엔티티 값을 new_temperature로 설정
            new_temperature = self.extract_last_temperature(entities)

            if new_temperature is None:
                dispatcher.utter_message(text="새로운 온도를 지정해주세요.")
                return []  # 새로운 온도가 지정되지 않으면 메서드를 종료

            for i in range(len(drink_types)):
                drink = drink_types[i]  # 변경할 음료의 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 변경할 음료의 수량
                size = sizes[i] if i < len(sizes) else "미디움"  # 음료의 사이즈
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션

                # 기존 주문에서 현재 온도를 가져옴
                current_temperature = temperatures[i] if i < len(temperatures) else None

                # 음료가 핫 드링크인데 새로운 온도가 아이스라면 에러 발생
                if drink in hot_drinks and new_temperature == "아이스":
                    raise ValueError(f"{drink}는(은) 아이스로 변경할 수 없습니다.")
                # 음료가 아이스 드링크인데 새로운 온도가 핫이라면 에러 발생
                if drink in ice_only_drinks and new_temperature == "핫":
                    raise ValueError(f"{drink}는(은) 핫으로 변경할 수 없습니다.")

                # 로그로 변경할 음료의 정보 출력
                logging.warning(f"변경 대상 음료: {drink}, 수량: {quantity}, 현재 온도: {current_temperature}, 새로운 온도: {new_temperature}, 사이즈: {size}, 추가 옵션: {additional_option}")

                try:
                    # 현재 주문된 음료를 기존 온도로 제거
                    order_manager.subtract_order(drink, quantity, current_temperature, size, additional_option)
                    # 새로운 온도로 주문 추가
                    order_manager.add_order(drink, quantity, new_temperature, size, additional_option)
                except ValueError as e:
                    # 오류 발생 시 사용자에게 메시지 전달
                    dispatcher.utter_message(text=str(e))
                    return []

            # 온도 변경 완료 메시지 생성 및 사용자에게 전달
            confirmation_message = f"온도를 변경하셨습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text=f"커피 온도 변경 중 오류가 발생했습니다: {str(e)}")
            return []