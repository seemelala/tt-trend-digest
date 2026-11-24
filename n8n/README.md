# n8n workflows

Two small workflows that use only built-in n8n nodes (Schedule Trigger, Set, HTTP Request, Code).
They do not need this repository's Python code. Tested on n8n 2.48.7.

| File | What it does | Calls | Cost |
| --- | --- | --- | --- |
| `github-trending-to-discord.json` | Once a day, posts the top 5 GitHub trending repositories as one Discord embed. | 1 per day | about $0.02 a month |
| `subreddit-new-posts-to-discord.json` | Every 15 minutes, posts new posts from one subreddit. The first run after you publish only saves what is there. | 96 per day | about $1.60 a month |

Prices are per 1,000 calls: $0.81 for `github/trending`, $0.56 for `reddit/subreddit_posts`.
Calls that return no data are not charged. Current prices: https://everyinfra.com/pricing

## Import

1. In n8n, open **Workflows > Add workflow**, then the **...** menu > **Import from File**, and pick one of the JSON files.
   You can also copy the file's content and paste it onto an empty canvas.
2. Get an EveryInfra API key: https://everyinfra.com/?utm_source=n8n-template
3. Open the HTTP Request node that calls EveryInfra. Under **Credential for Header Auth**, create a new credential:
   - Name: `Authorization`
   - Value: `Bearer YOUR_KEY`
4. In Discord, open the channel settings > **Integrations** > **Webhooks** > **New Webhook** > **Copy Webhook URL**.
5. Open the **Settings** node and paste the webhook URL into `discord_webhook_url`.
   For the subreddit workflow, also set `subreddit` (without `r/`).
6. Click **Execute workflow** once to check it, then click **Publish**
   (in n8n versions before 2.0, switch the workflow to **Active**).

## How the subreddit workflow avoids repeats

- It saves the ids of the posts it has seen in workflow static data. n8n saves static data only for
  runs of the published workflow, not for test runs in the editor.
- A test run (**Execute workflow**) posts the 3 newest posts, so you can check the channel. It does
  not change the saved ids.
- The first run after you publish only saves the ids of the current posts. Later runs send only
  posts with new ids.
- The ids are saved by the last node, **Remember sent posts**, which runs only after Discord accepts
  the message. If Discord rejects it or cannot be reached, the next run sends those posts again.
- Each run reads the 10 newest posts. If a subreddit gets more than 10 posts between two runs,
  the extra posts are skipped. Use a shorter interval for a very busy subreddit.
- If no posts come back, for example because the subreddit name is wrong, the run stops with an
  error that you can see in **Executions**. Such a call is still charged once, so fix the name.

## Notes

- Both HTTP Request nodes try up to 3 times, 5 seconds apart. When all tries fail, the run stops
  and the error is in **Executions**.
- Treat the Discord webhook URL like a password. Anyone who has it can post to your channel.
  If it leaks, delete the webhook in Discord and create a new one.
- Messages are sent with `allowed_mentions: { parse: [] }`, so nobody is pinged.
- To post somewhere other than Discord, change the Code node to build that service's message and
  point the **Send to Discord** node at its webhook.
- The GitHub workflow runs at 13:00 in the time zone of the workflow settings.
