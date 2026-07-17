import { redirect } from "next/navigation";

export default async function ScenarioWorkbenchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ date?: string }>;
}) {
  const { id } = await params;
  const { date } = await searchParams;
  const query = date ? `?date=${encodeURIComponent(date)}` : "";

  redirect(`/worldlines/${encodeURIComponent(id)}${query}`);
}
