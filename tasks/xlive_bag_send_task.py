from BiliClient import asyncbili
from .push_message_task import webhook
from .import_once import now_time
import logging
import math


async def send_gift(biliapi, roomid, uid, bag, gift_num = None):
    if gift_num is None:
        gift_num = bag['gift_num']
    ret = await biliapi.xliveBagSend(roomid, uid, bag["bag_id"], bag["gift_id"], gift_num)
    if ret["code"] == 0:
        bag['gift_num'] -= gift_num
        logging.info(f'{biliapi.name}: {ret["data"]["send_tips"]} {ret["data"]["gift_name"]} 数量{ret["data"]["gift_num"]}')
    return bag['gift_num'] == 0


async def xlive_bag_send_task(biliapi: asyncbili,
                              task_config: dict
                              ) -> None:
    room_id = task_config.get("room_id", 0)
    if room_id == 0:
        try:
            room_id = (await biliapi.xliveGetRecommendList())["data"]["list"][6]["roomid"]
        except Exception as e:
            logging.warning(f'{biliapi.name}: 获取直播间异常，原因为{str(e)}，跳过送出直播间礼物，建议手动指定直播间')
            webhook.addMsg('msg_simple', f'{biliapi.name}:直播送出礼物失败\n')
            return

    expire = task_config.get("expire", 172800)
    try:
        medal = (await biliapi.xliveFansMedal(1, 50))['data']['fansMedalList']
        bagList = sorted((await biliapi.xliveGiftBagList())["data"]["list"], key = lambda x: x['expire_at'])

        # lighting medals
        medals_to_send = [m for m in medal if m['is_lighted'] == 0]
        i = 0
        for m in medals_to_send:
            while i < len(bagList) and bagList[i]['gift_num'] <= 0:
                i += 1
            if i >= len(bagList):
                return
            i += send_gift(biliapi, m['roomid'], m['target_id'], bagList[i], 1)

        # send expire medals
        bagList = [bag for bag in bagList if bag['gift_num'] > 0 and expire > bag["expire_at"] - now_time > 0]
        if not bagList:
            logging.info(f'{biliapi.name}: 没有{expire}s内过期的直播礼物，跳过赠送')
            return
        i = 0
        price = {1: {'name': '辣条', 'price': 1},
                 6: {'name': '亿元', 'price': 10},
                 30607: {'name': '小心心', 'price': 50},
                 30610: {'name': '激爽刨冰', 'price': 1}, }
        for bag in bagList:
            empty = False
            while not empty:
                while i < len(medal) and medal[i]['today_intimacy'] >= medal[i]['day_limit']:
                    i += 1
                if i == len(medal):
                    i = 0
                send_gift(biliapi, medal[i]['roomid'], medal[i]['uid'], bag,
                          max(math.ceil((medal[i]['day_limit'] - medal[i]['today_intimacy']) / price[bag['gift_id']]['price']), 1))
        uid = (await biliapi.xliveGetRoomInfo(room_id))["data"]["room_info"]["uid"]
    except Exception as e:
        logging.warning(f'{biliapi.name}: 直播送出即将过期礼物异常，原因为{str(e)}')
        webhook.addMsg('msg_simple', f'{biliapi.name}:直播送出礼物失败\n')
