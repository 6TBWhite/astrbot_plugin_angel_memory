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
            return jsonify({"impulses": [], "confessions": [], "rejected": [], "total_weight": 0, "threshold": 0})

        return jsonify({
            "impulses": store.get_pending_impulses(),
            "confessions": store.get_pending_confessions(),
            "rejected": store.get_active_rejected(),
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

    async def test_trigger(self):
        """测试用：注入模拟触动"""
        impulse_store = self.plugin_context.get_component("impulse_store")
        if not impulse_store:
            return jsonify({"error": "触动存储不可用"}), 500

        belief_store = self.plugin_context.get_component("belief_store")
        if not belief_store or not belief_store.get_active_beliefs():
            return jsonify({"error": "暂无核心信念，请先添加信念再进行测试"}), 400

        impulse_store.add_impulse(
            content="用户反馈你的表达欲过高，在不太熟悉的人面前话太多让人不适",
            direction="表达欲需要在不熟悉的人面前收敛",
            trust_weight=1.5,
            source_users=["test_admin"],
        )
        impulse_store.add_impulse(
            content="多个用户表示你展开话题太快，还没建立足够信任就开始聊深入话题",
            direction="和不太熟的人要先建立信任再深入",
            trust_weight=1.0,
            source_users=["test_user1", "test_user2"],
        )
        impulse_store.add_impulse(
            content="你过于主动询问私人问题让人觉得冒犯",
            direction="对不熟的人要注意边界感",
            trust_weight=0.8,
            source_users=["test_user3"],
        )

        return jsonify({
            "status": "ok",
            "total_weight": impulse_store.get_pending_total_weight(),
            "threshold": impulse_store._threshold,
            "reached": impulse_store.is_threshold_reached(),
        })

    async def test_introspection(self):
        """测试用：手动触发自省（不新增触动）"""
        impulse_store = self.plugin_context.get_component("impulse_store")
        if not impulse_store:
            return jsonify({"error": "触动存储不可用"}), 500

        belief_store = self.plugin_context.get_component("belief_store")
        if not belief_store or not belief_store.get_active_beliefs():
            return jsonify({"error": "暂无核心信念"}), 400

        if not impulse_store.is_threshold_reached():
            return jsonify({"error": "触动权重未达自省阈值", "total_weight": impulse_store.get_pending_total_weight(), "threshold": impulse_store._threshold}), 400

        deepmind = self.plugin_context.get_component("deepmind")
        if deepmind and hasattr(deepmind, "_try_self_introspection"):
            await deepmind._try_self_introspection("__test_trigger__")

        return jsonify({
            "status": "ok",
            "confessions": len(impulse_store.get_pending_confessions()),
        })

    async def clear_rejected(self):
        """清空被拒缓冲区"""
        store = self.plugin_context.get_component("impulse_store")
        if not store:
            return jsonify({"error": "触动存储不可用"}), 500
        store._rejected_confessions = []
        store._save_to_file()
        return jsonify({"status": "ok"})
