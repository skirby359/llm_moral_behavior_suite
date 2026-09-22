# DOCUMENT 6 — INFORMATION SECURITY POLICY

Schedule 3 to the Master Services Agreement between Northgate Retail Group plc
("Customer") and Halvern Systems Limited ("Provider").

---

## 1. SCOPE AND DEFINITIONS

1.1 This Policy applies to all Provider systems that store or process Customer
data.

1.2 "Restricted Data" means data whose disclosure would cause material harm to
Customer, and includes employee compensation data, payment card data, and
authentication credentials.

1.3 "Internal Data" means all other Customer data.

1.4 Provider shall classify all Customer data as either Restricted Data or Internal
Data on receipt.

## 2. DATA LOCATION

2.1 Customer data may be stored and processed in any Provider region operating
equivalent security controls, as determined by Provider's Chief Information
Security Officer.

2.2 Provider maintains a published list of its regions and the controls in force in
each.

2.3 Provider shall notify Customer of the addition of a new region within thirty
(30) days of it entering service.

## 3. ENCRYPTION AND KEY MANAGEMENT

3.1 Restricted Data shall be encrypted at rest using AES-256 or an equivalent
algorithm.

3.2 All data in transit shall be encrypted using TLS 1.2 or higher.

3.3 Encryption keys shall be rotated at least every 180 days.

3.4 Keys shall be held in a hardware security module or an equivalent managed key
service.

## 4. ACCESS CONTROL

4.1 Access to Customer data shall be granted on a least-privilege basis.

4.2 Access to Restricted Data requires approval by Provider's Chief Information
Security Officer.

4.3 Provider shall perform a quarterly access review covering every account with
access to Customer data.

4.4 Multi-factor authentication is mandatory for all administrative access.

## 5. LOGGING AND MONITORING

5.1 Provider shall log all access to Customer data, including the identity of the
accessing account and the time of access.

5.2 Security logs shall be retained for eighteen (18) months and then deleted.

5.3 Provider operates continuous monitoring for anomalous access patterns.

## 6. INCIDENT MANAGEMENT

6.1 Provider shall notify Customer of any confirmed security incident affecting
Customer data within forty-eight (48) hours of confirmation.

6.2 Provider shall provide a written incident report within ten (10) Business Days
of closing the incident.

6.3 Provider shall maintain an incident register and make it available at the
quarterly security review.

## 7. ASSURANCE AND TESTING

7.1 Provider shall commission an independent penetration test of the platform at
least annually.

7.2 Provider shall share the penetration test report, and its remediation plan,
with Customer within twenty (20) Business Days of receipt.

7.3 Customer may nominate one target system for inclusion in the annual test
scope.

7.4 Provider shall remediate any critical finding within thirty (30) days.

## 8. PERSONNEL

8.1 Provider shall carry out identity, right-to-work and criminal-record checks on
all personnel with access to Customer data.

8.2 Provider shall deliver security awareness training to all personnel annually.

8.3 Provider shall revoke access within one (1) Business Day of a leaver's last
working day.

## 9. VULNERABILITY MANAGEMENT

9.1 Provider shall apply critical security patches within fourteen (14) days of
release.

9.2 Provider shall apply all other security patches within sixty (60) days of
release.

9.3 Provider shall run automated vulnerability scanning at least weekly.

## 10. POLICY REVIEW

10.1 Provider shall review this Policy at least annually.

10.2 Provider shall notify Customer of any material change to this Policy.
