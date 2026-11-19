# syntax=docker/dockerfile:1.7
# Rocket Lockett: the whole Minecraft server as one image, published to
# ghcr.io/vmenon04/rocket-lockett on a rocket-lockett-vX.Y.Z tag. Built from the repo root.
#
# Paper and every plugin are pinned here, each jar by its SHA-256, so nothing changes unless
# this file does. The world, player data and plugin data stay in the server's /data folder;
# the image only brings the jars and the settings below.

# AIBot, built from ../../aibot at the same commit.
FROM maven:3.9.16-eclipse-temurin-21 AS aibot
WORKDIR /src
COPY aibot/pom.xml .
RUN mvn -B -q dependency:go-offline
COPY aibot/src src
# The shaded jar is AIBot-<version>.jar; the unshaded one is original-AIBot-<version>.jar.
RUN mvn -B -q package && cp target/AIBot-*.jar /AIBot.jar

FROM itzg/minecraft-server:2026.11.0-java25
LABEL org.opencontainers.image.source=https://github.com/vmenon04/minecraft \
      org.opencontainers.image.description="Rocket Lockett: Paper with its plugins"

ENV TYPE=PAPER \
    VERSION=26.3 \
    PAPER_BUILD=256 \
    # Before syncing /plugins into /data/plugins, remove the jars there (only jars, only at the
    # top level), so a plugin dropped from this image doesn't linger. Plugin data folders stay.
    REMOVE_OLD_MODS=TRUE \
    REMOVE_OLD_MODS_INCLUDE=*.jar \
    REMOVE_OLD_MODS_DEPTH=1

# BlueMap 5.29: the 3D web map (served on 8100, shown at mc.vasumenon.com/map).
ADD --chmod=644 --checksum=sha256:7bf475936c26107d476c63151c76d5b49e865eebeada12c9e7d92155de877b9f \
    https://cdn.modrinth.com/data/swbUV1cr/versions/uHQIrUdf/bluemap-5.29-paper.jar /plugins/bluemap-5.29-paper.jar
# Simple Voice Chat 2.6.25 (UDP 24454).
ADD --chmod=644 --checksum=sha256:f39f2e840873aa08e0ccec733fdc824ed4c3b9282e027fd6f18a79006eebad20 \
    https://cdn.modrinth.com/data/9eGKb6K1/versions/5OqsnSs7/voicechat-bukkit-2.6.25.jar /plugins/voicechat-bukkit-2.6.25.jar
# EssentialsX: no stable release supports Minecraft 26.3 yet, so a development build that
# does (support landed on 2026-09-15), pinned by build number and checksum.
ADD --chmod=644 --checksum=sha256:5b8a1feb7c40a45d81e516bd077a7272d833c76cf829098743211999abd95929 \
    https://ci.ender.zone/job/EssentialsX/1833/artifact/jars/EssentialsX-2.22.1-dev+28-f8724e2.jar /plugins/EssentialsX-2.22.1-dev+28.jar
COPY --from=aibot /AIBot.jar /plugins/AIBot.jar
# Plugin settings kept here (BlueMap's), synced into /data/plugins at each start.
COPY servers/rocket-lockett/plugins/ /plugins/
