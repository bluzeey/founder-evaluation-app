import { caseA, caseB, caseC } from "./demoCases";

export const VALIDATION_SET = [caseA, caseB, caseC];

export const EXPECTED_ROUTES = [
  { caseId: caseA.id, expectedStatus: "ACTIVATION_READY" },
  { caseId: caseB.id, expectedStatus: "ASSOCIATE_REVIEW" },
  { caseId: caseC.id, expectedStatus: "VALIDATION_HOLD" },
];
