from typing import Dict, Any

from NotificationCenter.app.services.rabbitmq_handler import RabbitMQHandler
from NotificationCenter.app.config.settings import ALERT_QUEUE
from NotificationCenter.app.handlers.alert_smister_to_user_simulator import send_alert_to_user_simulator
from NotificationCenter.app.config.logging import setup_logging

logger = setup_logging("alert_consumer", "NotificationCenter/logs/alertConsumer.log")

class AlertConsumer:
    def __init__(self, rabbitmq_handler: RabbitMQHandler):
        self.rabbitmq = rabbitmq_handler
        logger.info("Alert Consumer initialized")

    def start_consuming(self):
        """Start consuming messages from the alert queue"""
        logger.info("Starting alert consumer")
        self.rabbitmq.consume_messages(
            queue_name=ALERT_QUEUE,
            callback=self.process_alert
        )

    def process_alert(self, alert_data: Dict[str, Any]):
        """Process incoming alert message"""
        try:
            logger.info(f"Received alert: {alert_data}")
            msg_type = alert_data.get("msgType")
            alert_identifier = alert_data.get("identifier")
            
            if msg_type in ["Alert", "Update"]:
                send_alert_to_user_simulator(self.rabbitmq, alert_data) 
            elif msg_type == "Cancel":
                stop_message = {
                    "msgType": "Cancel",
                    "id": alert_identifier,
                    "description": "Stop alert request from NotificationCenter"
                }
                send_alert_to_user_simulator(self.rabbitmq, stop_message)
        
            logger.info("Alert processed successfully")

        except Exception as e:
            logger.error(f"Error processing alert: {str(e)}")
            raise