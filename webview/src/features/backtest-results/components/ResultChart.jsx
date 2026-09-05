import { useMemo } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HighchartsChart } from "../../../shared/components/HighchartsChart.jsx";

export function ResultChart({ options, description, active, wide = false, children }) {
  const title = options.title?.text;
  const accessibleOptions = useMemo(() => ({
    ...options,
    title: { ...options.title, text: null },
    accessibility: {
      ...options.accessibility,
      enabled: true,
      description,
    },
  }), [description, options]);

  return (
    <Card className={`min-w-0 self-start ${wide ? "lg:col-span-2" : ""}`}>
      <CardHeader className="border-b">
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="overflow-hidden rounded-lg bg-background ring-1 ring-foreground/10">
          <HighchartsChart
            active={active}
            options={accessibleOptions}
            className={`w-full bg-background ${wide ? "h-[23.75rem]" : "h-[20.625rem]"}`}
            data-chart-surface="page-background"
          />
        </div>
        {children && <div className="mt-3">{children}</div>}
      </CardContent>
    </Card>
  );
}
