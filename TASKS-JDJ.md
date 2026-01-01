**1-1-26** HAPPY NEW YEAR JDJ..

[x] fix coder ✅ DONE 
  > ~~logic~~
  > ~~prompts(added project context injection to planner as well)~~
  > ~~optimizations and performance~~
  > ~~ensure it auto updates tasks list or Orchestrator~~ (added TaskList.update_task_status + disk persistence)
  > ~~clearly define agent roles again, re-assess need for 4..~~
  > ~~coder takes most token usage~~ (mitigated with context injection, pre-loaded artifacts)

[] implement "chats" or saved agent runs
  > can be utilized later for adaptive learning

**12-31-25**

[] Update manually coded components to use onsen ui
  > Also why two terminal components? is xterm only one used?
  > Fix xterm scrolling/interactivity 

[] Create settings menu UI with onsen
  > Adhere to brand colors
  > Opt-in settings for persistent adaptive agent learning (to send to main ships)
  > Agent autonomy options specific to ShipS platform
  > monaco editor settings tab
  > account settings
  
[] Add "step counting" to llm or otherwise hook into existing counting so its possible to undo to each reasoning step or tool call etc..
  > explore letting llm reset to a recent previous one in case of major errors?
  > use git perhaps?

[] Implement git integration
  > default monaco extension gui
  > possible versioning with llm steps?
  > SECURE

[] Address prompt injection + system revealing llm concerns
  > Intent agent can try to sanitize/translate broken english etc? 
  > Research modern ways to protect agentic systems 
  
[] Test all artifacts custom UI if applicable 
  > Default view should be artifacts drawer
  > Maybe have an overview section that shows them all compacted

[] LLM + Manual security audits
  > FastApi endpoints
  > agent integrations
  > all frontend/backend code

[] Risk/Pitfall matrix feature
  > may postpone to last in lieu of adaptive learning feature 