# minecraft

My Minecraft servers and what goes with them. Each folder builds and releases on its own tag;
[vmenon04/homelab](https://github.com/vmenon04/homelab) decides which versions run where.

| Folder | What it is | Release (tag) |
| --- | --- | --- |
| [`aibot/`](aibot) | `/ai <question>`: a Paper plugin that answers players' questions in chat | `AIBot-X.Y.Z.jar` on GitHub Releases (`aibot-vX.Y.Z`) |
| [`servers/rocket-lockett/`](servers/rocket-lockett) | The Rocket Lockett server: Paper and its plugins, pinned, as one image | `ghcr.io/vmenon04/rocket-lockett:X.Y.Z` (`rocket-lockett-vX.Y.Z`) |
| [`mc-site/`](mc-site) | [mc.vasumenon.com](https://mc.vasumenon.com): the servers' status and flatboy's stats | `ghcr.io/vmenon04/mc-site:X.Y.Z` (`mc-site-vX.Y.Z`) |

The web map at [mc.vasumenon.com/map](https://mc.vasumenon.com/map/) is BlueMap's own, served by the server image on port 8100; homelab's nginx in front of mc-site sends `/map/` there.

## A server image

A server's Dockerfile starts from [itzg/minecraft-server](https://docker-minecraft-server.readthedocs.io)
and pins Paper (`VERSION`, `PAPER_BUILD`) and every plugin jar by URL and SHA-256. At each
start the image's `/plugins` is synced into the server's `plugins/` folder, after removing the
jars there, so the running set of plugins is exactly the image's. Worlds, player data and
plugin data live in the server's data folder, never in the image.

To change a plugin: update its URL and checksum (`shasum -a 256 <jar>`), let CI start the server
with it, then tag a release. CI starts every server image with a fresh world and fails unless
Paper and each plugin load.

Renovate keeps the base images, Maven and Python dependencies and Actions current. It can't
follow the plugin URLs; check those by hand when updating Paper.

## Building

```sh
mvn -B -f aibot/pom.xml package                                     # aibot/target/AIBot-X.Y.Z.jar
docker build -f servers/rocket-lockett/Dockerfile -t rocket-lockett .
docker build -t mc-site mc-site && (cd mc-site && python -m pytest tests)
```

MIT licensed (see LICENSE).
