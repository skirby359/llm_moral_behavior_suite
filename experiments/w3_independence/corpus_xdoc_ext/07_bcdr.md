# DOCUMENT 7 — BUSINESS CONTINUITY AND DISASTER RECOVERY PLAN

Schedule 4 to the Master Services Agreement between Northgate Retail Group plc
("Customer") and Halvern Systems Limited ("Provider").

---

## 1. PURPOSE AND DEFINITIONS

1.1 This Plan sets out how Provider will maintain and restore the Services
following a disruptive event.

1.2 "Continuity Event" means any event that renders Provider's primary production
environment unavailable and cannot be resolved within normal support processes.

1.3 "Recovery Time Objective" or "RTO" means the target elapsed time between the
declaration of a Continuity Event and restoration of the Services.

1.4 "Recovery Point Objective" or "RPO" means the maximum period of data loss the
recovery process is designed to tolerate.

1.5 "Invocation" means Provider's formal declaration of a Continuity Event.

## 2. RECOVERY OBJECTIVES

2.1 Recovery Time Objective: eight (8) hours from Invocation.

2.2 Recovery Point Objective: twenty-four (24) hours.

2.3 These objectives apply to the production platform only. Non-production
environments have no stated objective.

## 3. RECOVERY SITE

3.1 Provider operates a secondary recovery environment in Frankfurt, Germany.

3.2 The recovery environment is maintained in a warm-standby configuration.

3.3 Data is replicated to the recovery environment on a scheduled basis consistent
with the Recovery Point Objective in clause 2.2.

## 4. INVOCATION

4.1 Only Provider's Head of Operations may declare an Invocation.

4.2 Provider shall inform Customer's nominated technical contact of an Invocation
as soon as reasonably practicable.

4.3 Provider shall provide status updates at intervals of not more than two (2)
hours during a Continuity Event.

## 5. EFFECT ON SERVICE LEVELS

5.1 Provider's obligations under the Service Level and Support Schedule are
suspended for the duration of a Continuity Event.

5.2 Invocation of this Plan may require up to twelve (12) hours of planned
unavailability while the Services are returned to the primary environment.

5.3 Periods of unavailability arising from a Continuity Event, and from the return
to the primary environment, are excluded from the availability calculation.

## 6. TESTING

6.1 Provider shall test this Plan at least once in every twelve (12) month period.

6.2 Provider shall give Customer not less than twenty (20) Business Days' notice of
a test.

6.3 Provider shall provide a test report within fifteen (15) Business Days of
completing a test.

6.4 Where a test fails to meet the objectives in clause 2, Provider shall produce a
remediation plan within one (1) month.

## 7. CUSTOMER RESPONSIBILITIES

7.1 Customer shall maintain current nominated technical and commercial contacts.

7.2 Customer shall participate in the annual test where Provider reasonably
requests it.

7.3 Customer shall maintain its own continuity arrangements for systems outside
Provider's scope.

## 8. DEPENDENCIES

8.1 This Plan assumes the continued availability of Provider's third-party
infrastructure supplier.

8.2 This Plan does not cover a simultaneous loss of both the primary and recovery
environments.

8.3 Provider shall review the dependency list at each annual test.

## 9. GOVERNANCE

9.1 The Plan is owned by Provider's Head of Operations.

9.2 The Plan shall be reviewed at least annually and after every Invocation.

9.3 Material changes to the Plan shall be notified to Customer.
