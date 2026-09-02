import { defineCollection, z } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({
      extend: z.object({
        activityId: z.string().optional(),
        kinds: z.array(z.string()).optional(),
        sourceId: z.string().optional(),
        traits: z.array(z.string()).optional(),
        printedPages: z.array(z.number().int().positive()).optional(),
        pdfPages: z.array(z.number().int().positive()).optional(),
        transcriptionStatus: z.string().optional(),
        translationStatus: z.string().optional(),
        safetyStatus: z.string().optional(),
      }),
    }),
  }),
};
