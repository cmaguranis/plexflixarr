# MdblistClient is a standalone utility (not used in the ingestion pipeline).
# Its batch_quality_check method makes real HTTP calls to api.mdblist.com;
# there is no value in mocking the entire HTTP layer for a passthrough client.
# Integration is verified manually or via the /discover/reorder endpoint.
