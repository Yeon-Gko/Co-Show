from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import logging
import re

class ActionCoffeeRecommendation(Action):
    def name(self) -> Text:
        return "action_coffee_recommendation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        recommended_coffees = ["아메리카노", "카페라떼", "카푸치노", "에스프레소"]
        recommended_coffees_str = ", ".join(recommended_coffees)
        recommedded_message = f"저희 매장이 추천하는 커피로는 {recommended_coffees_str} 등이 있습니다. 어떤 커피을 원하시나요?"
        # recommedded_message = f"{recommedded_text} {recommended_coffees_str} 등이 있습니다. 어떤 것을 원하시나요?"
        dispatcher.utter_message(text=recommedded_message)

        return []