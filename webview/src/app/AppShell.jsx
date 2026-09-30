import { ArrowLeft, ChevronDown, Download } from "lucide-react";
import { Menu } from "@base-ui/react/menu";

const menuItemClassName = "flex min-h-24 flex-col items-center justify-center gap-2 rounded-md px-3 py-3 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground data-disabled:pointer-events-none data-disabled:opacity-50";

function WindowsIcon() {
  return (
    <svg aria-hidden="true" data-testid="windows-icon" viewBox="0 0 24 24" className="size-8" fill="currentColor">
      <path d="M2 5.1 10.7 3.9v7.8H2V5.1Zm9.8-1.35L22 2.3v9.4H11.8v-7.95ZM2 12.8h8.7v7.8L2 19.4v-6.6Zm9.8 0H22v9.4l-10.2-1.45V12.8Z" />
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg aria-hidden="true" data-testid="apple-icon" viewBox="0 0 24 24" className="size-8" fill="currentColor">
      <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701" />
    </svg>
  );
}

export function AppHeader({ showBack = false, botUrls = {} }) {
  return (
    <header className="z-10 shrink-0 border-b bg-background/90 backdrop-blur-md">
      <div className="mx-auto grid w-full max-w-[100rem] grid-cols-[1fr_auto_1fr] items-center px-4 py-2 sm:px-6 lg:px-8">
        <div className="flex justify-self-start">
          {showBack && (
            <a
              href="/"
              aria-label="Back to strategies"
              className="inline-flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ArrowLeft aria-hidden="true" className="size-5" />
            </a>
          )}
        </div>
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
        <div className="flex justify-self-end">
          {showBack && (
            <Menu.Root>
              <Menu.Trigger
                aria-label="Download bot"
                className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-[#0f8eff] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#0878dc] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0f8eff] focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <Download aria-hidden="true" className="size-4" />
                <span>Download bot</span>
                <ChevronDown aria-hidden="true" className="size-4" />
              </Menu.Trigger>
              <Menu.Portal>
                <Menu.Positioner side="bottom" align="end" sideOffset={6} className="z-50 outline-none">
                  <Menu.Popup className="grid w-64 grid-cols-2 gap-1 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg outline-none">
                    {botUrls.windows ? (
                      <Menu.LinkItem href={botUrls.windows} download className={menuItemClassName}>
                        <WindowsIcon />
                        <span>Windows</span>
                      </Menu.LinkItem>
                    ) : (
                      <Menu.Item disabled className={menuItemClassName}>
                        <WindowsIcon />
                        <span>Windows</span>
                      </Menu.Item>
                    )}
                    {botUrls.mac ? (
                      <Menu.LinkItem href={botUrls.mac} download className={menuItemClassName}>
                        <AppleIcon />
                        <span>MacBook</span>
                      </Menu.LinkItem>
                    ) : (
                      <Menu.Item disabled className={menuItemClassName}>
                        <AppleIcon />
                        <span>MacBook</span>
                      </Menu.Item>
                    )}
                  </Menu.Popup>
                </Menu.Positioner>
              </Menu.Portal>
            </Menu.Root>
          )}
        </div>
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
