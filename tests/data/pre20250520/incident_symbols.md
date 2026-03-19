# Incident: *symbols outage with spiking load balancer 502s*

## All times in the same timezone: UTC

* **Incident Severity**: S4-LOW  
* **Incident Description**: symbols outage with spiking load balancer 502s  
* **Current Status**: Resolved
* **Incident Jira Ticket**: [SREIM-17](https://example.net/browse/SREIN-17) [IIM-17](https://example.net/browse/IIM-17)

* **Magnitude of Impact / Affected products:** Symbols files used to process some company products’ crash reports (including Firefox) could not be uploaded or downloaded.  
* **Start of Impact[^1]**: 2025-02-21 16:41  
* **Time of Discovery[^2]**: 2025-02-21 17:12  
* **Start of Incident[^3]**: 2025-02-21 19:37  
* **Time of Repair[^4]**: 2025-02-21 18:15  
* **Zoom link**: None  
* **Slack channel**: #incident-symbols-502-errors

## Who’s on point

*Not all of the following roles will be relevant to all incidents, fill in what’s needed.*

| Role | Name (slack handle) | Notes / supporting docs |
| :---- | :---- | :---- |
| **Incident Manager** | [Bianca](mailto:bianca@example.com) (@bianca) (through Feb 21, 2025\) [Amri](mailto:amri@example.com) (@amri) (after Feb 21, 2025\) |  |
| Comms | [Bianca](mailto:bianca@example.com) (@bianca) (through Feb 21, 2025\) [Amri](mailto:amri@example.com) (@amri) (after Feb 21, 2025\) | *Who is communicating to public (if needed)?  Who is communicating with execs?* |
| Engineering lead | [Sven](mailto:sven@example.com) (primary engineer) |  |
| Other (please enumerate) |  |  |

## Decisions

| What | When | Who | Notes |
| :---- | :---- | :---- | :---- |
|  |  |  |  |

# Details (Details are still being filled out)

At around 2025-02-21 16:41 UTC, Symbols started returning HTTP 502 errors for virtually all requests.

[https://grafana.example.net/goto/RT5cws5Hz?orgId=1](https://grafana.example.net/goto/RT5cws5Hz?orgId=1)

## Timeline (Timeline is still being filled out)

### 2025-02-21

* **16:41** \- Symbols started returning HTTP 502 errors for virtually all requests.  
* **16:44** \- Pingdom sends ops-team a downtime alert for symbols.  
* **16:52** \- [Amri](mailto:amri@example.com) posts a message about the outage in the Obs team private Slack channel.  
* **17:13** \- [Amri](mailto:amri@example.com) pings everyone in the channel about the outage with **@here**  
* **17:14** \- [Sven](mailto:sven@example.com) starts to investigate.  
* **17:16** \- [Sven](mailto:sven@example.com) realizes he accidentally deployed a Helm chart change he was experimenting with to prod instead of stage, using the stage values.  
* **17:30** \- [Sven](mailto:sven@example.com) redeploys the prod environment to revert all accidental changes: [https://github.com/company-services/symbols/actions/runs/13462049605](https://github.com/company-services/symbols/actions/runs/13462049605)  
* **17:39** \- [Sven](mailto:sven@example.com) notices that the load balancer had been recreated, the old Google-managed certificate got lost and the new one has not been created yet. He starts manually issuing a certificate.  
* **18:03** \- [Sven](mailto:sven@example.com) files PR to add manually issued certificate to the symbols load balancer: [https://github.com/company-it/webservices-infra/pull/4060](https://github.com/company-it/webservices-infra/pull/4060)  
* **18:07** \- [Sven](mailto:sven@example.com) deploys the change to pick up the manually issued certificate: [https://github.com/company-services/symbols/actions/runs/13462616859](https://github.com/company-services/symbols/actions/runs/13462616859)  
* **18:15** \- The change has fully propagated to Google's frontend servers

## Impact

* Symbols files used to process some company products’ crash reports (including Firefox) could not be uploaded or downloaded.

  * crash reports processed by Socorro during this time period won't have symbols--we'll need to reprocess them and then after that, everything will be fine


# Retrospective notes

## Action items

- [ ] Come up with a process to iterate on Helm chart changes in stage that does not involve locally running Helm. This will make the process less error-prone and more auditable. It's probably enough to add a parameter to select a different webservices-infra branch in our manual deployment playbooks. ([OBS-508](https://example.net/browse/OBS-508))  
- [ ] Make sure everyone on the team has access to the DNS records for our team. ([OBS-507](https://example.net/browse/OBS-507))  
- [ ] Fix ManagedCert resource for symbols prod to make it cover the prod domains again ([OBS-509](https://example.net/browse/OBS-509))

## Lessons learned

* [Sven](mailto:sven@example.com)  
  * Manually deploying to stage can be error-prone. I was generally aware of the danger. In the past, I always used to call Helm like this:

    	helm upgrade symbols . \-n symbols-stage \-f values-stage.yaml

    This explicitly includes a namespace argument, which ensures the deployment will fail when run against the wrong GKE cluster. I forgot to include this argument on Friday. I also don't remember changing the active kubectl context to the prod cluster, but given what happened I must have done it. I think it's necessary to be able to do quick stage deployments to iterate on Helm chart changes, but we should find a way to make it less error-prone.  
  * Changing the Helm values to the stage values had unexpected consequences. The deployment failed with Helm chart validation errors. I wasn't aware that I was deploying to prod at the time, but I was also sure that nothing should have changed if Helm shows validation errors. Yet, the changes ended up being partially applied. The workloads were completely unaffected, but other resources got updated with the stage values.  
  * In particular, the partial Helm deployment updated the ManagedCertificate resource to point to symbols-stage.symbols.nonprod.webservices.mozgcp.net. Redeploying with the prod values did not revert this change, and the ManagedCertificate in the prod environment still points to the wrong domain name, which is why it can't be issued. It's completely unclear to me why the accidental deployment did lead to an update of the ManagedCertificate resource, while the deployment to fix things did not.  
  * My tooling to quickly manually issue a certificate was broken. I had to manually come up with command lines for certbot, and manually update the TXT record in Infoblox, which delayed the fix by about 20 minutes. I haven't investigated how it broke yet.

# Addendum:

*Any additional information that may be of use.*   
*e.g.*

* *Captured output*  
* *sampled error*  
* *etc.*

---

## 

## History (don’t delete, move old info to below this line)

[^1]: The date and time the system started failing. This might not be known when the incident response is started, as the system might have been failing for a while before being noticed. It is fine to fill this in after the incident is resolved.

[^2]: The date and time an employee became aware of the failure. This is usually later in time compared to the “Start of Impact”

[^3]: The date and time the incident response process is started. This is the date and time the incident response document is created for the incident.

[^4]: The date and time the failing system starts operating normally again, e.g. users do not experience the failure anymore.
