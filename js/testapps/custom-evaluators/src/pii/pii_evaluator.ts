/**
 * Copyright 2024 Google LLC
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

import type { Genkit, ModelReference, z } from 'genkit';
import type { BaseEvalDataPoint, EvaluatorAction } from 'genkit/evaluator';
import type { ByoMetric } from '..';
import { piiDetectionScore } from './pii_detection';

export const PII_DETECTION: ByoMetric = {
  name: 'pii_detection',
};

/**
 * Create the PII detection evaluator.
 */
export function createPiiEvaluator<ModelCustomOptions extends z.ZodTypeAny>(
  ai: Genkit,
  judge: ModelReference<ModelCustomOptions>,
  judgeConfig: z.infer<ModelCustomOptions>
): EvaluatorAction {
  return ai.defineEvaluator(
    {
      name: `byo/${PII_DETECTION.name}`,
      displayName: 'PII Detection',
      definition: 'Detects whether PII is present in the output.',
    },
    async (datapoint: BaseEvalDataPoint) => {
      const score = await piiDetectionScore(judge, datapoint, judgeConfig);
      return {
        testCaseId: datapoint.testCaseId,
        evaluation: score,
      };
    }
  );
}
