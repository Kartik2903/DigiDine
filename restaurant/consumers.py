from channels.generic.websocket import AsyncWebsocketConsumer
import json

class OrderStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("orders", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("orders", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        # Broadcast the update to all clients
        await self.channel_layer.group_send(
            "orders",
            {
                "type": "order_status_update",
                "order_id": data["order_id"],
                "status": data["status"],
            }
        )

    async def order_status_update(self, event):
        await self.send(text_data=json.dumps({
            "order_id": event["order_id"],
            "status": event["status"],
        })) 