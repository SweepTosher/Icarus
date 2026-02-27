const SteamUser = require("steam-user");

const args = process.argv.slice(2);
let username = "";
let password = "";
let appid = 3224770;
let code = "";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--username") username = args[++i];
  else if (args[i] === "--password") password = args[++i];
  else if (args[i] === "--appid") appid = parseInt(args[++i]);
  else if (args[i] === "--code") code = args[++i];
}

if (!username || !password) {
  process.stderr.write(
    "Usage: node ticket_gen.js --username X --password Y [--code Z]\n"
  );
  process.exit(1);
}

const client = new SteamUser();

const loginOpts = {
  accountName: username,
  password: password,
};

if (code) {
  loginOpts.twoFactorCode = code;
}

client.logOn(loginOpts);

client.on("steamGuard", (domain, callback) => {
  process.stderr.write(
    "NEED_GUARD:" + (domain || "2fa") + "\n"
  );
  process.exit(2);
});

client.on("error", (err) => {
  process.stderr.write("ERROR:" + err.message + "\n");
  process.exit(1);
});

client.on("loggedOn", () => {
  process.stderr.write(
    "Logged in as " + client.steamID.getSteamID64() + "\n"
  );
  client.createAuthSessionTicket(appid, (err, sessionTicket) => {
    if (err) {
      process.stderr.write("Ticket error: " + err.message + "\n");
      process.exit(1);
    }
    const buf = Buffer.isBuffer(sessionTicket) ? sessionTicket : sessionTicket.sessionTicket || sessionTicket;
    const result = {
      steam_id: client.steamID.getSteamID64(),
      session_ticket: Buffer.from(buf).toString("hex").toUpperCase(),
    };
    process.stdout.write(JSON.stringify(result) + "\n");
    process.stderr.write(
      "Ticket generated (" + Buffer.from(buf).length + " bytes)\n"
    );
    setTimeout(() => process.exit(0), 500);
  });
});
