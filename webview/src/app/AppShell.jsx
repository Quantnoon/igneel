export function AppHeader() {
  return (
    <header className="z-10 shrink-0 border-b bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[100rem] items-center justify-center px-4 py-2 sm:px-6 lg:px-8">
        <h1 className="text-center font-heading text-base font-medium tracking-tight">
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
      </div>
    </header>
  );
}

export function AppShell({ children }) {
  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <AppHeader />
      <main className="relative min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
