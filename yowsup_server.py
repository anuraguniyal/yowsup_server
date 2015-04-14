from yowsup.layers.interface                           import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.protocol_messages.protocolentities  import TextMessageProtocolEntity
from yowsup.layers.protocol_receipts.protocolentities  import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities      import OutgoingAckProtocolEntity
from yowsup.layers import YowLayerEvent
from yowsup.layers.auth                        import YowAuthenticationProtocolLayer

import logging
import threading
import fortune
import json
import urllib2

def post_message_to_url(messageProtocolEntity, reply_url):
    logging.info("Posting message to %s"%reply_url)
    try:
        req = urllib2.Request(reply_url)
        req.add_header('Content-Type', 'application/json')
        data = {'from': messageProtocolEntity.getFrom(False), 'message':  messageProtocolEntity.getBody() }
        response = urllib2.urlopen(req, json.dumps(data))
        logging.info("response: %s"%response.read())
    except Exception,e:
        logging.error("Error: %s"%e)

class ServerLayer(YowInterfaceLayer):

    PROP_MESSAGES = "org.openwhatsapp.yowsup.prop.messages.queue" #list of (jid, message) tuples
    PROP_REPLY_URL = "org.openwhatsapp.yowsup.prop.reploy_url"
    EVENT_SEND_MESSAGE             = "org.openwhatsapp.yowsup.event.cli.send_message"

    lock = threading.Condition()

    def __init__(self):
        super(ServerLayer, self).__init__()

    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):
        if not messageProtocolEntity.isGroupMessage():
            if messageProtocolEntity.getType() == 'text':
                self.onTextMessage(messageProtocolEntity)
            elif messageProtocolEntity.getType() == 'media':
                self.onMediaMessage(messageProtocolEntity)

        receipt = OutgoingReceiptProtocolEntity(messageProtocolEntity.getId(), messageProtocolEntity.getFrom())
        #send receipt otherwise we keep receiving the same message over and over
        self.toLower(receipt)


    def onTextMessage(self, messageProtocolEntity):
        #send receipt otherwise we keep receiving the same message over and over
        logging.info("Text Message from %s: %s" % (messageProtocolEntity.getFrom(False), messageProtocolEntity.getBody() ))

        jid = self.getProp(YowAuthenticationProtocolLayer.PROP_CREDENTIALS)[0]
        if jid == messageProtocolEntity.getFrom(False):
            logging.warn("Message from myself, ignoring!!!")
            return

        reply_url = self.getProp(self.__class__.PROP_REPLY_URL)
        if reply_url is not None:
            post_message_to_url(messageProtocolEntity, reply_url)
            return

        msg = fortune.fortune()
        logging.info("replying with: %s"%msg)
        outgoingMessageProtocolEntity = TextMessageProtocolEntity(
            msg,
            to = messageProtocolEntity.getFrom())

        self.toLower(outgoingMessageProtocolEntity)

    def onMediaMessage(self, messageProtocolEntity):
        logging.info("media message type %s"%messageProtocolEntity.getMediaType() )
        if messageProtocolEntity.getMediaType() == "image":
            logging.info("Image url %s"%messageProtocolEntity.url)
        elif messageProtocolEntity.getMediaType() == "location":
            logging.info("Location %s %s"%(messageProtocolEntity.getLatitude(), messageProtocolEntity.getLongitude()))
        logging.info("Message IP: %s"%messageProtocolEntity.ip)

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        ack = OutgoingAckProtocolEntity(entity.getId(), "receipt", "delivery")
        self.toLower(ack)

    def onEvent(self, yowLayerEvent):
        self.lock.acquire()
        for target in self.getProp(self.__class__.PROP_MESSAGES, []):
            phone, message = target
            logging.info("Sending to: %s message: %s"%(phone, message))
            if '@' in phone:
                messageEntity = TextMessageProtocolEntity(message, to = phone)
            elif '-' in phone:
                messageEntity = TextMessageProtocolEntity(message, to = "%s@g.us" % phone)
            else:
                messageEntity = TextMessageProtocolEntity(message, to = "%s@s.whatsapp.net" % phone)

            self.toLower(messageEntity)

        self.setProp(self.__class__.PROP_MESSAGES, [])

        self.lock.release()

    @classmethod
    def send_message(cls, stack, to, body):
        cls.lock.acquire()
        messages = stack.getProp(cls.PROP_MESSAGES, [])
        messages.append((to, body))
        stack.setProp(cls.PROP_MESSAGES, messages)
        cls.lock.release()
        stack.broadcastEvent(YowLayerEvent(cls.EVENT_SEND_MESSAGE))


