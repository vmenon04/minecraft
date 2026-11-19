package com.vasumenon.aibot;

import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.concurrent.ConcurrentHashMap;

public class AIBot extends JavaPlugin {

    private final ConcurrentHashMap<String, Boolean> busyPlayers = new ConcurrentHashMap<>();

    @Override
    public void onEnable() {
        saveDefaultConfig();
        getLogger().info("AIBot enabled");
    }

    @Override
    public void onDisable() {
        getLogger().info("AIBot disabled");
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!command.getName().equalsIgnoreCase("ai")) return false;

        if (!(sender instanceof Player)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }

        Player player = (Player) sender;
        String playerName = player.getName();

        if (busyPlayers.getOrDefault(playerName, false)) {
            player.sendMessage("§cPlease wait for your previous AI response before sending another prompt.");
            return true;
        }

        if (args.length == 0) {
            player.sendMessage("§cUsage: /ai <message>");
            return true;
        }

        String userMessage = String.join(" ", args);
        String endpoint = getConfig().getString("ai_endpoint", "https://why.com/api/ultimate-search");

        String context = getConfig().getString("question_context",
                "This question comes from a player on a Minecraft Java Edition server, so answer it in the context of Minecraft: ");
        player.sendMessage("§7You: " + userMessage);

        busyPlayers.put(playerName, true);

        getServer().getScheduler().runTaskAsynchronously(this, () -> {
            try {
                String response = AIRequest.sendToAI(context + userMessage, endpoint);
                player.sendMessage("§bAI: " + response);
            } finally {
                busyPlayers.put(playerName, false);
            }
        });

        return true;
    }
}
