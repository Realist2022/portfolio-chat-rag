// Export the portfolio's projects into the corpus. Run from this repo's root:
//   node --experimental-strip-types scripts/export_projects.mts \
//     ../Portfolio-Sonny/src/data/projects.ts > corpus/projects/projects.json
// Only text fields are kept: images are not useful to retrieval.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const source = process.argv[2];
if (!source) {
  console.error("usage: export_projects.mts <path to projects.ts>");
  process.exit(1);
}
const { default: projects } = await import(pathToFileURL(resolve(source)).href);
const out = projects.map((p: any) => ({
  id: p.id,
  title: p.title,
  description: p.description,
  links: p.links ?? [],
  techStack: p.techStack ?? [],
}));
console.log(JSON.stringify(out, null, 2));
