/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// Grid section data for Project Montage landing page
const gridItems = [
  {
    icon: "solar:clapperboard-edit-outline",
    title: "Generate Storyboard",
    description:
      "Constructs a comprehensive multi-scene video storyboard derived from user conversation with uploaded visual assets.",
  },
  {
    icon: "solar:gallery-wide-outline",
    title: "Generate Image",
    description:
      "Generate new images, or modify the uploaded images through natural language prompts, utilizing the Nano Banana model.",
  },
  {
    icon: "solar:video-library-outline",
    title: "Generate Video",
    description:
      "Generate new videos based on user requirements powered by the advanced Veo generative model.",
  },
  {
    icon: "solar:maximize-square-minimalistic-linear",
    title: "Resize Image",
    description:
      "Utilizing Nano Banana to adjust image aspect ratios precisely while preserving core visual details and compositional integrity.",
  },
  {
    icon: "solar:videocamera-record-outline",
    title: "Concatenate Video",
    description:
      "Integrates multiple video segments into a singular, cohesive video.",
  },
  {
    icon: "solar:music-notes-outline",
    title: "Insert Preset BGM",
    description:
      "Enhances production value by overlaying background music presets onto the generated video.",
  },
  {
    icon: "solar:users-group-rounded-linear",
    title: "Select Character Asset",
    description:
      "Intelligently selects the most appropriate characters from a user-provided character assets for consistent integration into generated scenes.",
  },
];

// Function to render grid items
function renderGrid(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = gridItems
    .map(
      (item) => `
        <div
          class="tactile-base group transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_30px_60px_-15px_rgba(0,0,0,1)] hover:border-indigo-500/30 overflow-hidden flex flex-col h-64 border-transparent border rounded-2xl pt-6 pr-6 pb-6 pl-6 relative">
          <div class="mb-auto">
            <div
              class="w-12 h-12 rounded-xl tactile-inset flex items-center justify-center border border-zinc-800/50 mb-6 shadow-inner relative group-hover:border-indigo-500/50 transition-colors">
              <iconify-icon icon="${item.icon}" width="24" class="z-10 text-indigo-400 relative"
                height="24" style="color: rgb(129, 140, 248);"></iconify-icon>
            </div>
            <h3 class="text-lg font-normal text-zinc-100 tracking-tight">${item.title}</h3>
            <p class="leading-relaxed text-sm text-zinc-400 mt-2">${item.description}</p>
          </div>
          </div>
        </div>
    `,
    )
    .join("");
}
