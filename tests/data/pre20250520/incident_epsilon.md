# Incident: *2025-03-15 Epsilon down for 2-3hrs*

All times are written in UTC. use 24-hour clock and formatting via [https://en.wikipedia.org/wiki/ISO\_8601](https://en.wikipedia.org/wiki/ISO_8601)

* **Incident [Severity](https://example.net/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels)**: S2 \- High  
* **Incident Title**: Epsilon down  
* **Incident Jira Ticket**: [AUT-438](https://example.net/browse/AUT-438) [IIM-71](https://example.net/browse/IIM-71)   
* **Time of first Impact:** 2025-03-15 22:26 UTC  
* **Time Detected**: 2025-03-15 22:49 UTC (Pagerduty came in for epsilon being down)  
* **Time Alerted**: 2025-03-15 22:49 UTC (Pagerduty came in for epsilon being down)  
* **Time Acknowledge**: 2025-03-15 23:58 UTC  
* **Time Responded/Engaged**: 2025-03-15 23:58 UTC  
* **Time Mitigated (Repaired)**: 2025-03-15 00:20 UTC (GCP) / 2025-03-15 01:25 (AWS)  
* **Time Resolved**: 2025-03-15 00:20 UTC (GCP) / 2025-03-15 01:25 (AWS)  
* **Issue detected via: Automated Alert**  
* **Video call link**: Zoom
* **Slack channel**: \#2025-03-15-epsilon-connectivity  
* **Current Status**: \[**Resolved**\]

## Who’s on point

| Role | Name (slack handle) | Notes / supporting docs |
| :---- | :---- | :---- |
| **Incident Manager** | [Tom](mailto:tom@example.com) |  |
| **Comms** | [Tom](mailto:tom@example.com) | *Which one person is communicating inside company (to all)? Which one person is communicating with the public? Which one person is communicating with any other stakeholders not listed above (external partners, press, company execs, etc)?* |
| **Engineer(s)** | [Eric](mailto:eric@example.com)[Alex](mailto:alex@example.com) [Jon](mailto:jon@example.com) | *Put a parenthesis next to each person’s name who is working on this incident (during the incident, to resolve it), to help us identify any extra info about them that is pertinent to the problem (or, don’t leave a parentheses and just write names).* Examples: @nameA (primary on-call) @nameB (secondary on-call) @nameC (\<service-name\> engineer)  |
| Other (please enumerate) |  |  |

# Impact

*\<What is the impact of this incident? It’s ok to use “current tense” during the incident, and past-tense once you switch to writing the postmortem. For the postmortem, the opening statement of this section should be something like “on \<date\> from \<time1\> to \<time2\>, \<description of impact that was happening, and who was impacted\>.” Some things to consider covering:*

* *Are end-users not able to do something (e.g. 90% of Firefox users were unable to login to their company accounts)?*  
* *Are company engineers blocked from something (e.g. On \<date\> from \<time1\> to \<time2\> 100% of company engineers could not ship code to production. Though production was working ok, if one issue had arisen which needed a fast change we would have been unable to ship it)?*  
* *Are there risks of this getting worse, if so what things would contribute to that risk (e.g. time)?*

*/\>*

Effects:

* New add-ons and updated add-ons would not be able to get signed  
* Contents from Remote Settings would not be able to be resigned (a non-issue over the weekend outside of an emergency cert revocation)  
* Widevine DRM installs  
* Build Firefox (potentially an issue for emergency patches)  
  * Nightly builds might have been blocked  
* Firefox, Thunderbird, VPN updates

Due to the incident happening during the weekend we don’t think this caused a huge downward issue to our customers or end users. End user impact would have been near zero as we were not shipping updated remote-settings configs or application updates. Add-on signing could have slowed down an updated add-on release by a few hours during this outage. There were no known emergency patches going out at the time.

epsilon   
epsilon pod errors in log:

```
* uWSGI listen queue of socket "127.0.0.1:37699" (fd: 3) full !!! (101/100) *
```

^ It would be nice to have a clearer error spelled out, if possible. I was not able to quickly determine that epsilon was failing because Epsilon was down.

epsilon dashboard: [https://grafana.example.org/d/fRuT9IGZk/epsilon?orgId=1\&from=2025-03-15T21:21:56.420Z\&to=2025-03-16T01:35:17.171Z\&timezone=browser\&var-environment=prod\&var-containers=$\_\_all\&var-datasource=cdq6ttvymu4g0c\&refresh=30s](https://Grafana.example.org/d/fRuT9IGZk/epsilon?orgId=1&from=2025-03-15T21:21:56.420Z&to=2025-03-16T01:35:17.171Z&timezone=browser&var-environment=prod&var-containers=$__all&var-datasource=cdq6ttvymu4g0c&refresh=30s)

Specific panel showing 5xx errors on aus5: [https://grafana.example.org/d/fRuT9IGZk/epsilon?orgId=1\&from=2025-03-15T21:21:56.420Z\&to=2025-03-16T01:35:17.171Z\&timezone=browser\&var-environment=prod\&var-containers=$\_\_all\&var-datasource=cdq6ttvymu4g0c\&refresh=30s\&viewPanel=panel-37](https://Grafana.example.org/d/fRuT9IGZk/epsilon?orgId=1&from=2025-03-15T21:21:56.420Z&to=2025-03-16T01:35:17.171Z&timezone=browser&var-environment=prod&var-containers=$__all&var-datasource=cdq6ttvymu4g0c&refresh=30s&viewPanel=panel-37)

# Description of the issue

*\<A summary of the events that happened from the first moment of impact (even if we hadn’t detected the issue by then), what happened as we Detected (i.e. our alerts told us or a user told us), Acknowledged (e.g. we ACK’d the page, even if we didn’t start to work no it), Responded/Engaged (i.e. we started working on it)\>, Mitigated (we stopped the impact from being material, even if temporarily), Resolved (we ensured the impact will not return for a substantial amount of time, even with a temporary fix in place, until we take on longer term postmortem action items.)\>*

It appears related to [Cert expire for Epsilon](https://docs.google.com/document/d/doc1/edit?tab=t.0#heading=h.qoodesll7nc2) on 2025-03-14 but did not show until today (2025-03-15) when the scheduled K8 pods were restarted via cron job. This caused the epsilon service to crash which in turn caused epsilon to fail and alert us.

Grafana Graphs showing pods failing to complete startup process successfully

[Autograph config](https://example.com/company-services/autograph-config/pull/24) was set to ignore epsilon warnings from Monitor because we knew epsilon was going to take a bit to get them updated. Unfortunately we didn’t remember to remove those bad signer configs and didn’t realize a bad signer config would take autograph down.

# Contributing Factors

*\<Why did this issue happen? Not just at a surface level, but be sure to probe into the causes for anything which happened that wasn’t ideal. The goal is to find the multiple, possibly related (but possibly not related), contributing factors, the confluence of which culminated into this incident. For example instead of traditional “5 why’s” think about “multiple tree’s of why’s” \- avoid the temptation/pitfall of looking for “just one root cause.” ([read more here](https://www.kitchensoap.com/2012/02/10/each-necessary-but-only-jointly-sufficient/))\>*

* Autograph pod restart should have been done during business hours on 2025-03-14  
  * Especially with the root certificate refresh we should have done a manual restart after the certificates expired  
  * Restart happens every day to handle end-entity certs and intermediates expiring and creating new keys/certs  
* We should have certificates expire during business hours  
* Autograph was migrating from AWS to GCP and alerts were not setup on GCP metrics  
* Autograph should not have failed to restart because of expired certificates  
* Autograph checks the certificate more frequently then the restart but the alerts were muted due to epsilon migration  
* epsilon required more time to migrate from AWS to GCP  
  * Missed communication between epsilon and Autograph that they are no longer using the certificate

# Postmortem Action Items

*\<What are we going to do to prevent recurrence of this issue in our domain, prevent potentially similar issues this incident+postmortem has made us realize are risks, and/or help others in company prevent these types of issues; this should include tangible actions resulting from things like “lessons learned”; this should include links to jira tickets which are filed for every postmortem action item. **This section is not complete (thus the postmortem is not ‘done’) until jira tickets have been created with ETAs (tentative dates are ok), linked to the ticket for this incident, and listed in the table below**\>*

| Jira Ticket | Context / Summary / Reason |
| :---- | :---- |
| \[[AUT-430](https://example.net/browse/AUT-430)\] | Clean-up to remove the aus signer from the ignored list. (helps address the Autograph failure not notifying the Autograph team) |
| \[[AUT-411](https://example.net/browse/AUT-411)\] | Add GCP graph and pagerduty for alerts in Grafana. (helps address the Autograph failure not notifying the Autograph team) |
| \[[AUT-433](https://example.net/browse/AUT-433)\] | An expired cert shouldn't cause autograph startup to crash |
| \[[AUT-216](https://example.net/browse/AUT-216)\] | Monitor breaks should alert us |
| \[[AUT-437](https://example.net/browse/AUT-437)\] | Create an inventory of all the keys in the AWS CloudHSM and reassess when the CloudHSM should be deprecated |
| \[[AUT-367](https://example.net/browse/AUT-367)\] | Establish SLO for Autograph. |
|  | Figure out alerting from the customers to the Autograph team during off-hours. Spell out a clear way for our customers to page us after hours should they need to reach us. |
| \[[Bugz 1960009](https://bugz.example.com/show_bug.cgi?id=1960009)\] | epsilon should report errors with more clarity/verboseness. Eric had no way to easily identify that Autograph was causing epsilon to fail |
| \[Alex to do\] | Tag our followup items with \`incident-action-items\` in Jira/Github. |
|  | Talk [Hamid](mailto:hamid@example.com) and [Cassandra](mailto:cassandra@example.com) about updating the incident process like using Jira ticket to track incident  |
| \[Hamid or Cassandra will create\] | Infra Incident Management process needs a mechanism (e.g. specific label in jira) to help categorize incidents as Postmortem Action Items |
| \[Hamid or Cassandra will create\] | Infra Incident Management needs to publish guidance for being able to page-in help from other teams during an incident (and take the steps to implement first) |

# \[optional\] Postmortem discussion notes

*\<Anything we want to capture as notes during postmortem discussion. This could be a place to capture notes (who said/shared what, etc). However this is not a place where any form of follow-up or action items go. Instead, those should go into the Postmortem Action Items section. Notice this postmortem doc doesn’t have a “lessons learned” section (or other similar ones), that too goes into Postmortem Action items (if it’s not worth taking specific steps to improve, then it arguably wasn’t a “lesson learned”). **The best version of this section is when it is left blank** because all the postmortem discussion focused on ensuring the previous sections were correct, and resulted in Postmortem Action Items which helped prevent recurrence of this issue and ones like it across as much of the company as possible.\>*

* \[Girish\] Would this have been worse if it happened during the week?  
  * Yes, devs in the company and our workflows for releasing things were impacted so those would have not been able to proceed until it was fixed.  
* \[Girish\] Are there other services which would be subject to similar impact in the future?  
  * There shouldn’t be other services like this. All have been migrated to GCP V2. We’ve also updated cert expirations to Tuesdays (avoids monday holidays, keep us mid-week).

# \[optional\] Addendum:

*\<Any additional information that may be of use. For example:*

* *Captured output*  
* *sampled error*  
* *etc.*

*/\>*

## Timeline

*\<After the incident is done, please move this section to the bottom of the document/\>*

| YYYY MM DD @ hh:mm UTC | Person(s) | Note/comment/action |
| :---- | :---- | :---- |
| **Day before** |  | Old root cert expires on March 14th, afternoon in US. |
| **18:00** |  | Autograph pods restarted causing a failure |
| **22:49** |  | Pagerduty notification about epsilon being down |
| **22:55** | [Eric](mailto:eric@example.com) | Starts working the epsilon issue and is unable to get it stable |
| **23:40** | [Eric](mailto:eric@example.com) | Calls SRE incident Commander (Tom) |
| **23:40** | [Mathieu](mailto:mathieu@example.com) | Notifies that Autograph seems to be down and is impacting AMO developer signing |
| **23:45** | [Tom](mailto:tom@example.com) | Starts incident process |
| **23:47** | [Tom](mailto:tom@example.com) | Calls [Jon](mailto:jon@example.com) |
| **23:59** |  | Incident declared |
| **00:01** | [Jon](mailto:jon@example.com)[Eric](mailto:eric@example.com) | Jon walks Eric through troubleshooting as he was away from office |
| **00:01** | [Eric](mailto:eric@example.com) | Discovers that Autograph lost all activity at 15:26 which caused a downstream failure for epsilon and discovers the following error: {"msg":"failed to add signer \\"aus\\": contentsignaturepki \\"aus\\": failed to initialize end-entity: contentsignaturepki \\"aus\\": failed to verify x5u: failed to verify certificate chain: certificate 2 \\"root-ca-production-amo\\" expired: notAfter=2025-03-14 22:53:57 \+0000 UTC"}} |
| **00:03** | [Tom](mailto:tom@example.com) [Alex](mailto:alex@example.com) | Tom calls Alex to help remove the expired signer |
| **00:06** | [Jon](mailto:jon@example.com) | ”We forgot to remove this expired signer from prod, because it was still being used for old VPN clients…” |
| **00:16** |  | [Alex](mailto:alex@example.com)creates PR and is approved ([link](https://example.com/company-services/autograph-config/pull/40))This PR is targeting the prod GCP environment and removes the signer configuration (aus, epsilon) that used the expired cert. |
| **00:25** |  | New code fix confirmed to fix the Autograph start issue for prod GCP. This was our main problem to resolve (old AWS only used for ESR and release builds at this point) |
| **00:32** |  | [Mathieu](mailto:mathieu@example.com)confirmed the issue with AMO is resolved and things recovered |
| **00:33** |  | [Alex](mailto:alex@example.com)backports same fix into the AWS Jenkins version of Autograph ([link](https://example.com/company-services/autograph-config/pull/42)) and ([fixing corrupted sops file](https://example.com/company-services/autograph-config/pull/43)). This removed old signer configs for the AWS config files.  |
| **00:45** |  | [Alex](mailto:alex@example.com)deploys code to AWS Stage, confirms working (via heartbeat) The prod SOPS config file somehow got corrupted in the first commit and Alex manually fixed. |
| **01:39** |  | [Alex](mailto:alex@example.com)deploys code to AWS Prod, confirms working  (via heartbeat) |
| **01:40** |  | Incident Resolved |
|  |  |  |
|  |  |  |
