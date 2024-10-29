from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from dev.jung.meta.actions.kiosk import OrderManager, OrderMapper
import logging
import order_utils
import re


class ActionAddAdditionalOption(Action):
    def name(self) -> Text:
        return "action_add_additional_option"
    
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            order_manager = OrderManager()
            order_mapper =OrderMapper()   

            # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            # 엔티티를 start 값을 기준으로 정렬
            entities.sort(key=lambda e: e['start'])
            
            # 'add' 엔티티의 인덱스를 찾기
            add_indices = [i for i, entity in enumerate(entities) if entity['entity'] == 'add']
            
            # 'add' 엔티티가 하나만 있는 경우 모든 옵션을 추가
            if len(add_indices) == 1:
                logging.warning(f"add 엔티티 하나 있음")
                # OrderMapper를 사용하여 엔티티를 매핑
                mapper = OrderMapper(entities)
                temperatures, drink_types, sizes, quantities, add_additional_options = mapper.get_mapped_data()

                # 디버깅을 위한 로그 출력
                logging.warning(f"추가 옵션 추가 입력 내용: {entities}")
                logging.warning(f"추가 옵션 추가 매핑 데이터: {temperatures, drink_types, sizes, quantities, add_additional_options}")


#   # 추가(5번)
#             if order_manager.orders in drink_types and temperatures and sizes:
#                     dispatcher.utter_message(text=f"기존 메뉴인 {drink_types}에 추가 할까요? 아니면 새 {drink_types}를 주문 하시겠습니까?:", buttons=[
#                     {"title": "기존 메뉴에 추가는 '추가' 라 말해주세요", "payload": f"/add_additional_options{'additional_options':{add_additional_options}}"},
#                     {"title": "새 메뉴 주문은 '주문' 이라 말해주세요", "payload": f"/order_coffee{'order_drink':{drink_types}}"}
#                 ])
#                 # 추가
#             else:

                # 음료 속성 검증
                order_manager.raise_missing_attribute_error(mapper.drinks)  

                # 매핑된 데이터를 사용하여 주문 정보 업데이트
                for i in range(len(drink_types)):
                    drink = drink_types[i]  # 음료 종류
                    quantity = quantities[i] if quantities[i] is not None else 1  # 잔 수
                    temperature = temperatures[i] if i < len(temperatures) else "핫"  # 온도
                    size = sizes[i] if i < len(sizes) else "미디움"  # 사이즈
                    add_additional_options = add_additional_options[i] if i < len(add_additional_options) else []  # 추가 옵션

                    current_option = []

                    # 디버깅을 위한 로그 출력
                    logging.warning(f"현재 옵션: {current_option}")
                    logging.warning(f"추가 옵션: {add_additional_options}")

                    if add_additional_options:
                        # add_additional_options 메서드를 호출하여 추가 옵션 추가
                        order_manager.add_additional_options(drink, quantity, temperature, size, current_option, add_additional_options)

                # 최종 확인 메시지 생성 및 사용자에게 전달
                confirmation_message = f"말씀하신 옵션이 추가 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
                dispatcher.utter_message(text=confirmation_message)

                return []

            # 'add' 엔티티가 2개 이상인 경우
            elif len(add_indices) > 1:
                logging.warning(f"add 엔티티 여러개 있음")
                # 마지막 'add' 엔티티의 인덱스
                last_add_index = add_indices[-1]

                # 마지막 'add' 엔티티 이전의 엔티티를 매핑
                before_last_add_entities = entities[:last_add_index]
                # 마지막 'add' 엔티티 이후의 엔티티 중 'additional_options' 엔티티만 추출
                between_add_entities = entities[add_indices[-2] + 1:last_add_index]
                
                logging.warning(f"마지막 add 엔티티 이전 : {before_last_add_entities}")
                logging.warning(f"마지막 add 엔티티 사이의 엔티티 : {between_add_entities}")

                # 마지막 'add' 엔티티 이전의 엔티티를 매핑
                current_mapper = OrderMapper(before_last_add_entities)
                current_temperatures, current_drink_types, current_sizes, current_quantities, current_additional_options = current_mapper.get_mapped_data()

                # 'additional_options' 엔티티만 추출
                add_additional_options = [entity['value'] for entity in between_add_entities if entity['entity'] == 'additional_options']

                # 현재 옵션에서 추가 옵션을 제거
                # current_additional_options가 문자열이라면 split하여 리스트로 변환
                current_additional_options_list = []
                for option in current_additional_options:
                    current_additional_options_list.extend(option.split(', '))

                # 추가 옵션에서 중복 제거된 항목만 남기기
                current_additional_options = [
                    option for option in current_additional_options_list
                    if option not in add_additional_options
                ]

                # 추가 옵션 표준화
                order_mapper.standardize_option
                add_additional_options = [order_mapper.standardize_option(option) for option in add_additional_options]

                # 디버깅을 위한 로그 출력
                logging.warning(f"현재 옵션: {current_additional_options}")
                logging.warning(f"추가 옵션: {add_additional_options}")

                # 현재 옵션과 추가 옵션을 비교하여 업데이트
                for i in range(len(current_drink_types)):
                    drink = current_drink_types[i]  # 음료 종류
                    quantity = current_quantities[i] if current_quantities[i] is not None else 1  # 잔 수
                    temperature = current_temperatures[i] if i < len(current_temperatures) else "핫"  # 온도
                    size = current_sizes[i] if i < len(current_sizes) else "미디움"  # 사이즈
                    current_option = current_additional_options[i] if i < len(current_additional_options) else []  # 현재 추가 옵션

                    logging.warning(f"업뎃: {drink, quantity, temperature, size, current_option}")

                    if current_option:
                        # 추가 옵션으로 업데이트
                        order_manager.add_additional_options(drink, quantity, temperature, size, current_option, add_additional_options)

                # 최종 확인 메시지 생성 및 사용자에게 전달
                confirmation_message = f"말씀하신 옵션이 추가 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
                dispatcher.utter_message(text=confirmation_message)

                return []

        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text="추가 옵션 추가 중 문제가 발생했습니다. 다시 시도해 주세요.")
            # 예외 상세 로그 출력
            logging.exception("Exception occurred in action_add_additional_option")
            return []
