export function AppHeader({ center, end }) {
  return (
    <header className="z-10 shrink-0 border-b bg-background/90 backdrop-blur-md">
      <div className="mx-auto grid min-h-20 w-full max-w-[100rem] grid-cols-1 items-center gap-3 px-4 py-3 sm:grid-cols-[1fr_auto_1fr] sm:px-6 lg:px-8">
        <h1 className="text-center font-heading text-base font-medium tracking-tight sm:text-left">
          <a
            href="https://quantnoon.com"
            target="_blank"
            rel="noreferrer"
            className="rounded-md outline-none transition-colors hover:text-foreground/80 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="text-muted-foreground">powered by </span>
            <span className="font-semibold text-foreground"><img src="/logo.png" alt="Quantnoon Logo" className="inline-block h-6 w-6 ml-2 -mt-2 -mr-[2px] text-[#0d8cfd]" />uantnoon</span>
          </a>
        </h1>
        {center ?? <div aria-hidden="true" className="hidden sm:block" />}
        {end ?? <div aria-hidden="true" className="hidden sm:block" />}
      </div>
    </header>
  );
}

export function AppShell({ children, center, end }) {
  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <AppHeader center={center} end={end} />
      <main className="relative min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
