import json
import time
import queue
from typing import Any
from common.config import GCP_PROJECT, HMAC_SECRET_KEY
from common.identity import sign_payload
from common.schemas import MessageEnvelope

class PubSubManager:
    """
    Pub/Sub messaging client.
    Supports in-memory message queue fallback for standalone local execution.
    """
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.publisher = None
        self.subscriber = None
        
        if not use_mock:
            try:
                from google.cloud import pubsub_v1
                self.publisher = pubsub_v1.PublisherClient()
                self.subscriber = pubsub_v1.SubscriberClient()
            except Exception as e:
                print(f"[PubSubManager] Cloud Pub/Sub initialization skipped/failed ({e}), using in-memory bus.")
                self.use_mock = True

        if self.use_mock:
            self._topics = {}  # topic_name -> queue.Queue()

    def _get_mock_queue(self, topic_name: str) -> queue.Queue:
        if topic_name not in self._topics:
            self._topics[topic_name] = queue.Queue()
        return self._topics[topic_name]

    def publish_message(self, topic_name: str, sender_id: str, payload_type: str, payload: dict[str, Any]) -> str:
        signature = sign_payload(payload, HMAC_SECRET_KEY)
        msg_id = f"msg-{int(time.time() * 1000)}"
        envelope = MessageEnvelope(
            message_id=msg_id,
            sender_id=sender_id,
            target_topic=topic_name,
            payload_type=payload_type,
            payload=payload,
            signature=signature,
            timestamp=time.time()
        )

        data_bytes = envelope.model_dump_json().encode("utf-8")

        if self.use_mock:
            q = self._get_mock_queue(topic_name)
            q.put(envelope)
            return msg_id

        topic_path = self.publisher.topic_path(GCP_PROJECT, topic_name)
        future = self.publisher.publish(topic_path, data=data_bytes)
        return future.result()

    def pull_mock_messages(self, topic_name: str, timeout: float = 1.0) -> list[MessageEnvelope]:
        if not self.use_mock:
            return []
        q = self._get_mock_queue(topic_name)
        messages = []
        start = time.time()
        while time.time() - start < timeout:
            try:
                msg = q.get_nowait()
                messages.append(msg)
            except queue.Empty:
                break
        return messages
