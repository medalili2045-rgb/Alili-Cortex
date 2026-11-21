import json
import unittest

from alili_engine.d1_dispatch_store import D1BrainDispatchStore


class FakeStatement:
    def __init__(self, db, sql):
        self.db = db
        self.sql = sql
        self.values = ()

    def bind(self, *values):
        self.values = values
        return self

    async def first(self):
        return self.db.first(self.sql, self.values)

    async def all(self):
        return self.db.all(self.sql, self.values)

    async def run(self):
        return self.db.run(self.sql, self.values)


class FakeD1:
    def __init__(self):
        self.rows = {}

    def prepare(self, sql):
        return FakeStatement(self, sql)

    async def first(self, sql, values):
        if "WHERE dispatch_id" in sql:
            row = self.rows.get(values[0])
            return dict(row) if row else None
        raise AssertionError(sql)

    async def all(self, sql, values):
        rows = list(self.rows.values())
        if "WHERE status" in sql:
            rows = [row for row in rows if row["status"] == values[0]]
            limit = values[1]
        else:
            limit = values[0]
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return {"results": [dict(row) for row in rows[:limit]]}

    async def run(self, sql, values):
        if sql.lstrip().startswith("INSERT"):
            dispatch_id, created, updated, status, objective, plan_json = values
            if dispatch_id in self.rows:
                raise ValueError("duplicate")
            self.rows[dispatch_id] = {
                "dispatch_id": dispatch_id, "created_at": created,
                "updated_at": updated, "status": status, "objective": objective,
                "plan_json": plan_json, "result_json": None, "error_code": None,
            }
        elif sql.lstrip().startswith("UPDATE"):
            status, updated, result_json, error_code, dispatch_id = values
            row = self.rows[dispatch_id]
            row.update({"status": status, "updated_at": updated, "error_code": error_code})
            if result_json is not None:
                row["result_json"] = result_json
        else:
            raise AssertionError(sql)


class D1BrainDispatchStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = FakeD1()
        self.store = D1BrainDispatchStore(self.db)
        self.plan = {"objective": "test task", "assignments": [{"brain_id": "ac_reasoning"}]}

    async def test_create_update_get_round_trip(self):
        created = await self.store.create_brain_dispatch(
            "ac-dispatch-123", "test task", self.plan
        )
        self.assertEqual(created["status"], "queued")
        self.assertEqual(created["plan"], self.plan)
        result = {"status": "completed_pending_review", "finalized": False}
        updated = await self.store.update_brain_dispatch(
            "ac-dispatch-123", "completed_pending_review", result=result
        )
        self.assertEqual(updated["result"], result)
        self.assertEqual((await self.store.get_brain_dispatch("ac-dispatch-123"))["status"],
                         "completed_pending_review")

    async def test_list_with_status_filter(self):
        await self.store.create_brain_dispatch("ac-dispatch-1", "one", self.plan)
        await self.store.create_brain_dispatch("ac-dispatch-2", "two", self.plan)
        await self.store.update_brain_dispatch("ac-dispatch-2", "blocked")
        all_items = await self.store.list_brain_dispatches(limit=10)
        blocked = await self.store.list_brain_dispatches(status="blocked", limit=10)
        self.assertEqual(len(all_items), 2)
        self.assertEqual([item["dispatch_id"] for item in blocked], ["ac-dispatch-2"])

    async def test_rejects_invalid_inputs_and_unknown_ids(self):
        with self.assertRaisesRegex(ValueError, "invalid_dispatch_id"):
            await self.store.create_brain_dispatch("bad", "test", self.plan)
        with self.assertRaisesRegex(ValueError, "invalid_dispatch_limit"):
            await self.store.list_brain_dispatches(limit=0)
        with self.assertRaises(KeyError):
            await self.store.update_brain_dispatch("ac-dispatch-missing", "failed")

    async def test_rejects_oversized_plan(self):
        with self.assertRaisesRegex(ValueError, "dispatch_plan_too_large"):
            await self.store.create_brain_dispatch(
                "ac-dispatch-large", "test", {"data": "x" * 100_001}
            )


if __name__ == "__main__":
    unittest.main()
