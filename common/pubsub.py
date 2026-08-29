import json
import time
import queue
from typing import Any, Optional
from common.config import GOOGLE_CLOUD_PROJECT, HMAC_SECRET_KEY, USE_PUBSUB
from common.identity import sign_payload
from common.schemas import MessageEnvelope

class PubSubManager:
    """
    Pub/Sub messaging client.
    Supports in-memory message queue fallback for standalone local execution.
    """
    def __init__(self, use_mock: Optional[bool] = None):
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            self.use_mock = not USE_PUBSUB

        self.publisher = None
        self.subscriber = None
        self.backend_mode = "in-memory bus"
        self._topics = {}  # topic_name -> queue.Queue()

        if not self.use_mock:
            try:
                from google.cloud import pubsub_v1
                self.publisher = pubsub_v1.PublisherClient()
                self.subscriber = pubsub_v1.SubscriberClient()
                self.backend_mode = "Pub/Sub (production)"
                print(f"[PubSubManager] Initialized: Pub/Sub production (project={GOOGLE_CLOUD_PROJECT})")
            except Exception as e:
                print(f"[PubSubManager] Cloud Pub/Sub initialization skipped/failed ({e}), using in-memory bus.")
                self.use_mock = True
                self.backend_mode = "in-memory bus"
        else:
            print("[PubSubManager] Initialized: in-memory bus mode")

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

        # Always record in local queue for in-process subscriber visibility
        q = self._get_mock_queue(topic_name)
        q.put(envelope)

        if self.use_mock or not self.publisher:
            return msg_id

        try:
            data_bytes = envelope.model_dump_json().encode("utf-8")
            topic_path = self.publisher.topic_path(GOOGLE_CLOUD_PROJECT, topic_name)
            future = self.publisher.publish(topic_path, data=data_bytes)
            # Non-blocking or caught result
            res = future.result(timeout=5.0)
            return res
        except Exception as e:
            print(f"[PubSubManager] Cloud publish to '{topic_name}' failed ({e}). Retained in local bus.")
            return msg_id

    def pull_mock_messages(self, topic_name: str, timeout: float = 1.0) -> list[MessageEnvelope]:
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
