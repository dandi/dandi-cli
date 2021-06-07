#!/usr/bin/env python3
import click

from dandi.dandiapi import DandiAPIClient
from dandi.girder import GirderCli


def adhoc_list_girder(_id, client, prefix=""):
    """Pure girder API has no recursive listing, so let's do it manually"""
    for r in client.listItem(_id):
        assert r.get("_modelType", None) == "item"
        f = list(client.listFile(r["_id"]))
        if len(f) == 0:
            print(f"  Empty item with prefix={prefix}: {r}")
            continue
        if len(f) != 1:
            print("Multiple files for an item still found!")
            print(f)
            import pdb

            pdb.set_trace()
        else:
            f = f[0]
            assert f["size"] == r["size"]
        yield (f"{prefix}{r['name']}", r["size"])

    for r in client.listFolder(_id, "folder"):
        assert r.get("_modelType", None) == "folder"
        yield from adhoc_list_girder(r["_id"], client, f"{prefix}{r['name']}/")


@click.command()
def main():
    g_client = GirderCli("http://3.19.164.171")
    a_client = DandiAPIClient("https://api.dandiarchive.org/api")

    with a_client.session():
        g_client.dandi_authenticate()
        # gather all dandisets known to girder: hardcoded _id for "drafts" collection
        g_dandisets = list(
            g_client.listFolder("5e59bb0af19e820ab6ea6c62", "collection")
        )
        for dandiset, girder_id in [(x["name"], x["_id"]) for x in g_dandisets]:
            if dandiset != "000026":
                continue
            print(f"DANDI:{dandiset}", end="\t")
            g_meta, g_assets_ = g_client.get_dandiset_and_assets(girder_id, "folder")
            g_assets = list(g_assets_)
            # harmonize and get only what we care about ATM - path and size,
            # or otherwise we would need to query each asset for metadata
            g_assets_h = set((a["path"].lstrip("/"), a["size"]) for a in g_assets)

            # Yarik trusts nobody.  Two identical bugs are less likely!
            g_assets_adhoc = set(adhoc_list_girder(girder_id, g_client))

            if g_assets_h != g_assets_adhoc:
                print("ad-hoc and dandi listing of girder differs!")
                import pdb

                pdb.set_trace()

            a_meta, a_assets_ = a_client.get_dandiset_and_assets(dandiset, "draft")
            a_assets = list(a_assets_)
            a_assets_h = set((a["path"].lstrip("/"), a["size"]) for a in a_assets)

            if a_assets_h != g_assets_h:
                print("differs")
                import pdb

                pdb.set_trace()
            else:
                print(f"{len(a_assets)} assets the same")


if __name__ == "__main__":
    main()
