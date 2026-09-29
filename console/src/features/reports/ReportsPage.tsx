import { FileText, Signature } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { Button } from "@/design/components/Button";
import { useCan } from "@/lib/access";
import { Page } from "../shell/Page";
import { Card, CardHeader } from "@/design/components/Surface";
import { ExportCard } from "./ExportCard";
import { ExportsPanel } from "./ExportsPanel";
import { SnapshotsSection } from "./SnapshotsSection";
import { KeyCard, PipelinesCard, VerifyCard } from "./TrustCards";

export default function ReportsPage() {
  const navigate = useNavigate();
  const canSign = useCan("reports.sign");
  const [signOpen, setSignOpen] = useState(false);
  const { hash } = useLocation();
  // "Show All" in the downloads popover lands on the export list.
  useEffect(() => {
    if (hash !== "#exports") return;
    const t = window.setTimeout(() => document.getElementById("exports")?.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
    return () => window.clearTimeout(t);
  }, [hash]);
  return (
    <Page
      title="Reports"
      subtitle="Standard, verifiable evidence of your cryptography: a CycloneDX cryptography bill of materials, SARIF for code scanning, SPDX, and snapshots signed with post-quantum cryptography."
      actions={
        <>
          <Button variant="bordered" icon={<FileText />} onClick={() => navigate("/brief")}>
            Executive brief
          </Button>
          {canSign && (
            <Button variant="filled" icon={<Signature />} onClick={() => setSignOpen(true)}>
              Sign snapshot
            </Button>
          )}
        </>
      }
    >
      <ExportCard />
      <Card id="exports" className="mt-4 scroll-mt-20">
        <CardHeader title="Exports" subtitle="Everything you have exported, newest first, and where it is saved." />
        <ExportsPanel />
      </Card>
      <SnapshotsSection signOpen={signOpen} onSignOpenChange={setSignOpen} />
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <KeyCard />
        <VerifyCard />
      </div>
      <div className="mt-4">
        <PipelinesCard />
      </div>
    </Page>
  );
}
