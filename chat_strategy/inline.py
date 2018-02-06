import json

from telegram import InlineQuery, InlineQueryResultAudio

import Storage
# from ChatActor import ChatActor
from Storage import DbList


def on_query(q, chat_actor):

    q = q # type: InlineQuery
    chat_actor = chat_actor # type: ChatActor

    liked_tracks_db = chat_actor.context.storage.ask(
        {'command': 'get_list', 'name': Storage.LIKED_TRACKS_TABLE, "suffix": q.from_user.id}) # type: DbList
    liked_tracks = liked_tracks_db.get(limit=10, order="DESC", offset=0 if q.offset is None or len(str(q.offset)) == 0 else q.offset)
    res = []
    for track in liked_tracks:
        track = json.loads(track)
        res.append(InlineQueryResultAudio(str(q.from_user.id)  + "_"+ str(track.get("file_id")), chat_actor.get_d_url(track.get("file_id")), track.get("title"), performer=track.get("artist"), audio_duration=track.get("duration")))
    chat_actor.context.bot.tell({"command":"inline_res", "q":q, "res": res})
