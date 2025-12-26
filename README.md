

## **DESIGN PHILOSOPHY**

**Prevention > Detection > Repair**

Each agent is designed around *specific failure modes* rather than generic "do coding" tasks. This makes the system:
- **Explainable**: Each agent has a clear reason to exist
- **Efficient**: Agents only run when their failure mode is possible
- **Measurable**: Success = pitfalls caught

---

Component	Responsibility

FastAPI	Agents, orchestration, spawning builds, log streaming, lifecycle
Vite Frontend	User interaction, chat, artifacts, commands
Electron	Preview display only
User Dev Server	Actual app runtime (Vite/Next/etc)