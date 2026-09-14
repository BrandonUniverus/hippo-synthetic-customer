<#--
  Based on base/login/info.ftl from Keycloak 26.7.0. The base template prints
  message.summary as both the title and the first paragraph whenever no
  messageHeader is supplied ("You are signed out" twice); this version shows
  the summary once.
-->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>
            ${kcSanitize(msg("${messageHeader}"))?no_esc}
        <#else>
            ${message.summary}
        </#if>
    <#elseif section = "form">
    <div id="kc-info-message">
        <#if messageHeader?? || requiredActions??>
            <p class="instruction">${message.summary}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list><#else></#if></p>
        </#if>
        <#if skipLink??>
        <#else>
            <#if pageRedirectUri?has_content>
                <p><a href="${pageRedirectUri}">${msg("backToApplication")}</a></p>
            <#elseif actionUri?has_content>
                <p><a href="${actionUri}">${msg("proceedWithAction")}</a></p>
            <#elseif (client.baseUrl)?has_content>
                <p><a href="${client.baseUrl}">${msg("backToApplication")}</a></p>
            <#else>
                <p><a href="${properties.kcLogoLink!'/'}">${msg("nl.backToNorthlake")}</a></p>
            </#if>
        </#if>
    </div>
    </#if>
</@layout.registrationLayout>
