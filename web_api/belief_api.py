"""
核心信念 API

支持 WebUI 上查看和管理 OC 的核心信念。
"""

from __future__ import annotations

from quart import jsonify, request

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class BeliefAPI:
    def __init__(self, plugin_context):
        self.plugin_context = plugin_context

    def _get_belief_store(self):
        return self.plugin_context.get_component("belief_store")

    async def list_beliefs(self):
        store = self._get_belief_store()
        if not store:
            return jsonify({"beliefs": []})

        beliefs = store.get_active_beliefs()
        return jsonify({"beliefs": beliefs})

    async def add_belief(self):
        store = self._get_belief_store()
        if not store:
            return jsonify({"error": "核心信念存储不可用"}), 500

        data = await request.get_json()
        if not data:
            return jsonify({"error": "缺少请求体"}), 400

        content = str(data.get("content", "")).strip()
        if not content:
            return jsonify({"error": "content 不能为空"}), 400

        bid = store.add_belief(
            content=content,
            origin="WebUI手动添加",
            approved_by="admin",
        )
        return jsonify({"id": bid, "content": content})

    async def modify_belief(self):
        store = self._get_belief_store()
        if not store:
            return jsonify({"error": "核心信念存储不可用"}), 500

        data = await request.get_json()
        if not data:
            return jsonify({"error": "缺少请求体"}), 400

        belief_id = str(data.get("belief_id", "")).strip()
        content = str(data.get("content", "")).strip()

        if not belief_id or not content:
            return jsonify({"error": "belief_id 和 content 不能为空"}), 400

        try:
            store.modify_belief(belief_id, content)
            return jsonify({"status": "ok", "id": belief_id})
        except ValueError as e:
            return jsonify({"error": str(e)}), 404

    async def delete_belief(self):
        store = self._get_belief_store()
        if not store:
            return jsonify({"error": "核心信念存储不可用"}), 500

        data = await request.get_json()
        if not data:
            return jsonify({"error": "缺少请求体"}), 400

        belief_id = str(data.get("belief_id", "")).strip()
        if not belief_id:
            return jsonify({"error": "belief_id 不能为空"}), 400

        store.remove_belief(belief_id)
        return jsonify({"status": "ok", "id": belief_id})

    async def list_impulses(self):
        store = self.plugin_context.get_component("impulse_store")
        if not store:
            return jsonify({"impulses": [], "confessions": [], "total_weight": 0, "threshold": 0})

        return jsonify({
            "impulses": store.get_pending_impulses(),
            "confessions": store.get_pending_confessions(),
            "total_weight": store.get_pending_total_weight(),
            "threshold": store._threshold,
        })

    async def dismiss_confession(self):
        store = self.plugin_context.get_component("impulse_store")
        if not store:
            return jsonify({"error": "触动存储不可用"}), 500

        data = await request.get_json()
        if not data:
            return jsonify({"error": "缺少请求体"}), 400

        confession_id = str(data.get("confession_id", "")).strip()
        if not confession_id:
            return jsonify({"error": "confession_id 不能为空"}), 400

        store.dismiss_confession(confession_id)
        return jsonify({"status": "ok", "id": confession_id})
