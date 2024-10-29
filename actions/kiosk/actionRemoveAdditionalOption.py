from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import order_utils
import logging
import re

class ActionRemoveAdditionalOption(Action):
    def name(self) -> Text:
        return "action_remove_additional_option"
    
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            order_manager = OrderManager()
            order_mapper =OrderMapper()

            # 엔티티를 정렬하고 매핑
            mapper = OrderMapper(entities)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 디버깅을 위한 로그 출력
            logging.warning(f"추가 옵션 제거 입력 내용: {entities}")
            logging.warning(f"추가 옵션 제거 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            
            order_utils.raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 제거할 옵션이 없으면 사용자에게 메시지 출력하고 종료
            if not additional_options:
                dispatcher.utter_message(text="제거할 옵션을 지정해주세요.")
                return []

            # 매핑된 데이터를 사용하여 주문 정보 업데이트
            for i in range(len(drink_types)):
                drink = drink_types[i]  # 음료 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 잔 수
                temperature = temperatures[i] if i < len(temperatures) else "핫"  # 온도
                size = sizes[i] if i < len(sizes) else "미디움"  # 사이즈
                current_additional_option = additional_options[i] if i < len(additional_options) else None  # 현재 추가 옵션

                if current_additional_option:
                    # 현재 옵션에서 중복된 옵션 제거
                    current_options = list(set(current_additional_option.split(", ")))
                    last_remove_option = current_options[-1]  # 마지막 옵션을 제거할 옵션으로 설정

                    # 중복된 옵션이 있는지 확인 후 제거할 옵션 설정
                    for option in reversed(current_options):
                        if current_additional_option.count(option) > 1:
                            last_remove_option = option
                            break

                    logging.warning(f"제거해야할 옵션 : {last_remove_option}, 현재 주문되어 있는 옵션 : {current_options}")

                    order_manager.remove_additional_options(drink, quantity, temperature, size, current_options, last_remove_option)

            # 최종 확인 메시지 생성 및 사용자에게 전달
            confirmation_message = f"말씀하신 옵션이 제거 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(f"추가 옵션 제거 중 문제가 발생했습니다. 다시 시도해 주세요.")
            return []