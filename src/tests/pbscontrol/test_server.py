import responses

from tests.pbscontrol.testcase import PBSControlTestcase


class PBSServerTestcase(PBSControlTestcase):

    def test_version(self):
        assert self.server.version["version"] == "4.1.1"
        assert self.server.version["release"] == "4.1"

    def test_datastores_loaded(self):
        assert len(self.server.datastores) == len(self.datastores)
        store_names = [ds["store"] for ds in self.server.datastores]
        assert "datastore1" in store_names
        assert "datastore2" in store_names

    @responses.activate
    def test_datastore_usage(self):
        for ds in self.datastores:
            self.responses_get(f"/api2/json/admin/datastore/{ds['store']}/status")

        usage = self.server.datastore_usage

        assert len(usage) == len(self.datastores)

        ds1 = next(u for u in usage if u["store"] == "datastore1")
        assert ds1["total"] == 1_000_000_000_000
        assert ds1["used"] == 400_000_000_000
        assert ds1["avail"] == 600_000_000_000
        assert ds1["gc-status"] == "ok"

        ds2 = next(u for u in usage if u["store"] == "datastore2")
        assert ds2["total"] == 2_000_000_000_000
        assert ds2["used"] == 1_800_000_000_000
        assert ds2["avail"] == 200_000_000_000

    @responses.activate
    def test_datastore_usage_with_gc_error(self):
        datastores_with_error = [
            {**self.datastores[0], "gc-status": {"error": "some gc error"}},
            self.datastores[1],
        ]
        from tests.pbscontrol.fixtures.api import create_response_wrapper

        responses_get = create_response_wrapper(datastores_with_error)
        for ds in datastores_with_error:
            responses_get(f"/api2/json/admin/datastore/{ds['store']}/status")

        usage = self.server.datastore_usage
        ds1 = next(u for u in usage if u["store"] == "datastore1")
        assert ds1["gc-status"] == "some gc error"

        ds2 = next(u for u in usage if u["store"] == "datastore2")
        assert ds2["gc-status"] == "ok"
