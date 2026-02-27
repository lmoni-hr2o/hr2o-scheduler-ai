from google.cloud import datastore
e = datastore.Entity()
print(f"Is Entity a dict? {isinstance(e, dict)}")
import collections.abc
print(f"Is Entity a Mapping? {isinstance(e, collections.abc.Mapping)}")
print(f"Is Entity a MutableMapping? {isinstance(e, collections.abc.MutableMapping)}")
