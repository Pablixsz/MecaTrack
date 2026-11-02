# Video script (optional, 1-3 minutes)

**1. Intro (15 s)**
"This is MecaTrack, a booking and vehicle tracking system for a car repair workshop. In this lab we hardened its quality and security pipeline."

**2. SonarCloud (30 s)** - Open the project summary.
"The first analysis found 32 bugs and 15 vulnerabilities. The Quality Gate now passes, with no open issues of type bug or vulnerability and 97 percent coverage. Some code smells remain open, and five findings were closed with a written justification instead of a code change. Evidence tooling is outside the analysis scope."

**3. Mutation testing (20 s)** - Show the CI run and the failing demo.
"Mutmut went from 62.6 to 98.4 percent on the scheduling and payment logic. If the score drops below 50 percent, the build fails. Here is that failure on a temporary branch."

**4. JWT demo (40 s)** - Run in a terminal:
- `POST /api/auth/login` returns a token.
- `GET /api/rbac/admin` with an admin token returns 200.
- The same endpoint with a client token returns 403.
- A request without a token returns 401.

**5. OWASP summary (25 s)** - Open `docs/lab7/owasp-controls.md`.
"We implemented controls for nine of the ten OWASP API Security risks, each with an automated test. For example, one client cannot read another client's appointments, and login is limited to five attempts per minute. The table also lists known limitations."

**6. Critical evaluation of an AI suggestion (30 s)**
"Here is a suggestion that was wrong. The AI added a catch call to every line that Sonar flagged for unhandled promises. Three of those calls were on a synchronous function, which would have crashed the admin and mechanic screens when clearing filters. The next Sonar analysis caught it, we reviewed all 26 calls and fixed those three. The lesson is to verify AI fixes, not just accept them because a warning disappeared."

> Adjust this section if you prefer another example. GitHub Copilot was not used in this lab, so do not mention it as a tool used unless that changes.
