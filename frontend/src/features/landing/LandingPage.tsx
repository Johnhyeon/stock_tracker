import { Link } from 'react-router-dom'

const promisePoints = [
  { label: 'Server Processing', value: '0 events' },
  { label: 'Data Ownership', value: 'User 100%' },
  { label: 'API Key Storage', value: 'Local only' },
]

const featureCards = [
  {
    title: 'BYOK Connectors',
    description: 'Users connect their own API keys (KIS, OpenDART, and others) directly in their local environment.',
  },
  {
    title: 'Local Collection Pipeline',
    description: 'Scheduler, cache, and retry logic are included so data collection runs on the buyer machine only.',
  },
  {
    title: 'Chart Insight Dashboard',
    description: 'Ready-to-sell UI components for signal cards, chart panels, and YouTube demo screens.',
  },
]

const policyPoints = [
  'API keys are entered and used only on the customer PC.',
  'Raw data is stored in local database files, not in our server.',
  'This product sells source code and workflow, not market data itself.',
]

const plans = [
  {
    name: 'Starter Code Pack',
    price: 'KRW 149,000',
    description: 'For solo creators',
    bullets: ['1 landing page + 1 dashboard', 'Base API connector modules', 'Setup guide and sample config'],
    highlighted: false,
  },
  {
    name: 'Pro Creator Bundle',
    price: 'KRW 390,000',
    description: 'For sales and operation',
    bullets: ['2 landing pages + 3 dashboards', 'Full local collection pipeline', 'YouTube demo script templates'],
    highlighted: true,
  },
]

export default function LandingPage() {
  return (
    <div className="landing-shell min-h-screen text-slate-100">
      <div className="landing-grid fixed inset-0 -z-10" />
      <div className="mx-auto max-w-6xl px-6 py-8 md:px-10 md:py-12">
        <header className="flex items-center justify-between rounded-2xl border border-white/15 bg-white/5 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-blue-500 text-xs font-bold text-slate-900">
              ST
            </div>
            <p className="landing-title text-lg font-bold">Stock Tracker Code Shop</p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="#pricing"
              className="rounded-lg border border-white/20 px-3 py-2 text-sm text-white/90 transition hover:bg-white/10"
            >
              Pricing
            </a>
            <Link
              to="/"
              className="rounded-lg bg-cyan-300 px-3 py-2 text-sm font-semibold text-slate-900 transition hover:bg-cyan-200"
            >
              View Demo
            </Link>
          </div>
        </header>

        <section className="relative mt-10 grid items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <span className="inline-flex rounded-full border border-cyan-200/30 bg-cyan-300/10 px-3 py-1 text-xs font-semibold tracking-wide text-cyan-200">
              LOCAL-RUN + BYOK MODEL
            </span>
            <h1 className="landing-title text-4xl font-extrabold leading-tight md:text-6xl">
              Sell the code.
              <br />
              Users run data locally.
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-slate-200/85 md:text-lg">
              This is not a data resale service. You deliver connectors, local collection logic, and dashboard UI.
              Buyers run everything with their own API keys on their own machines.
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="#pricing"
                className="rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-cyan-200"
              >
                See Packages
              </a>
              <a
                href="#policy"
                className="rounded-xl border border-white/20 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                How It Works
              </a>
            </div>
          </div>

          <div className="landing-float rounded-3xl border border-cyan-100/20 bg-slate-950/70 p-4 shadow-[0_25px_80px_rgba(8,145,178,0.25)] backdrop-blur">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-sm font-semibold text-cyan-100">Runtime Flow</p>
              <span className="rounded-full bg-emerald-400/20 px-2 py-1 text-xs font-semibold text-emerald-300">
                NO SERVER
              </span>
            </div>
            <div className="space-y-2 rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm">
              <p className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">1) User enters API keys</p>
              <p className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">2) Local collector runs</p>
              <p className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">3) Local DB is updated</p>
              <p className="rounded-lg border border-cyan-200/30 bg-cyan-300/10 px-3 py-2 text-cyan-100">
                4) Dashboard renders insights
              </p>
            </div>
            <p className="mt-3 text-xs text-slate-300">
              Data stays on user hardware. Your infrastructure is not in the data path.
            </p>
          </div>
        </section>

        <section className="mt-10 grid gap-3 rounded-2xl border border-white/15 bg-white/[0.03] p-4 md:grid-cols-3">
          {promisePoints.map((item) => (
            <div key={item.label} className="rounded-xl border border-white/10 bg-slate-950/50 px-4 py-5">
              <p className="text-xs tracking-wide text-slate-300">{item.label}</p>
              <p className="mt-2 text-2xl font-bold text-cyan-100">{item.value}</p>
            </div>
          ))}
        </section>

        <section id="features" className="mt-14">
          <p className="text-sm font-semibold tracking-wider text-cyan-200/80">WHAT YOU SELL</p>
          <h2 className="landing-title mt-2 text-3xl font-bold md:text-4xl">Code assets for your YouTube product funnel</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {featureCards.map((item) => (
              <article
                key={item.title}
                className="rounded-2xl border border-white/15 bg-white/[0.04] p-5 transition hover:-translate-y-1 hover:bg-white/[0.07]"
              >
                <h3 className="text-lg font-bold text-cyan-100">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-200/85">{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="policy" className="mt-14 rounded-2xl border border-amber-200/25 bg-amber-200/5 p-6">
          <p className="text-sm font-semibold tracking-wider text-amber-200/80">OPERATING PRINCIPLES</p>
          <h2 className="landing-title mt-2 text-3xl font-bold md:text-4xl">Transparent model for buyers</h2>
          <div className="mt-5 space-y-2 text-sm text-slate-200/90">
            {policyPoints.map((item) => (
              <p key={item}>- {item}</p>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-300">
            Buyers are responsible for complying with each API provider terms. Product scope is code and workflow only.
          </p>
        </section>

        <section id="pricing" className="mt-14">
          <p className="text-sm font-semibold tracking-wider text-cyan-200/80">PRICING</p>
          <h2 className="landing-title mt-2 text-3xl font-bold md:text-4xl">One-time code package pricing</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {plans.map((plan) => (
              <article
                key={plan.name}
                className={`rounded-2xl border p-6 ${plan.highlighted ? 'border-cyan-200/40 bg-cyan-300/10 shadow-[0_18px_60px_rgba(34,211,238,0.25)]' : 'border-white/15 bg-white/[0.03]'}`}
              >
                <p className="text-sm text-slate-300">{plan.description}</p>
                <h3 className="landing-title mt-1 text-2xl font-bold">{plan.name}</h3>
                <p className="mt-3 text-4xl font-extrabold text-cyan-100">
                  {plan.price}
                  <span className="ml-1 text-base font-medium text-slate-300">/one-time</span>
                </p>
                <div className="mt-4 space-y-2 text-sm text-slate-200/85">
                  {plan.bullets.map((bullet) => (
                    <p key={bullet}>- {bullet}</p>
                  ))}
                </div>
                <button
                  className={`mt-6 w-full rounded-xl px-4 py-3 text-sm font-semibold transition ${plan.highlighted ? 'bg-cyan-300 text-slate-900 hover:bg-cyan-200' : 'border border-white/20 bg-white/5 hover:bg-white/10'}`}
                >
                  Contact Sales
                </button>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
