"""email templates"""

html_template = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html>
        <head>
            <meta name="viewport" content="width=device-width">
            <meta http-equiv="Content-Type" content="text/html charset=UTF-8" />
            <style type="text/css">
                @media only screen and (max-width: 480px){{
                    #templateColumns{{
                        width:100% !important;
                    }}

                    .templateColumnContainer{{
                        display:block !important;
                        width:100% !important;
                    }}

                    .columnContent{{
                        font-size:16px !important;
                        line-height:125% !important;
                    }}

                    .leftColumnContent{{
                        font-size:16px !important;
                        line-height:125% !important;
                    }}

                    .rightColumnContent{{
                        font-size:16px !important;
                        line-height:125% !important;
                    }}
                }}
            </style>
        </head>
        <body>
            <table border="0" cellpadding="0" cellspacing="0" height="100%" width="100%" id="bodyTable" style="background-color: #E0E0E0;;">
                <tr>
                    <td align="center" valign="top">
                        <table border="0" cellpadding="10" cellspacing="0" width="600" id="emailContainer" >
                            <tr>
                                <td align="center" valign="top" style="font-family:Helvetica;">
                                    <table border="0" cellpadding="20" cellspacing="0" width="100%" id="emailBody" style="background-color: #ffffff; border: 1px solid #BBBBBB;border-collapse: collapse !important;">
                                        <tr>
                                            <td align="center" valign="top" background="https://ui.adsabs.harvard.edu/styles/img/background.jpg" style="width:100%; background-color: #150E35" >
                                                <img src="https://ui.adsabs.harvard.edu/styles/img/ads_logo.png" alt="Astrophysics Data System" style="width: 70%; color: #ffffff; font-size: 34px; font-family: Helvetica;"/>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" valign="top" style="width:100%; background-color: #ffffff;">
                                                <h2 style="margin-top: 0;margin-right: 0;margin-bottom: 10px;margin-left: 0;"> myADS Personal Notification Service </h2>
                                                <h3 style="margin-top: 0;margin-right: 0;margin-bottom: 10px;margin-left: 0;"> Weekly email for Jane Smith </h3>
                                                <h3 style="margin-top: 0;margin-right: 0;margin-bottom: 10px;margin-left: 0;"> July 23, 2019 </h3>
                                            </td>
                                        </tr>
                                        <tr>
                                            <table border="0" cellpadding="0" cellspacing="0" width="100%" id="templateColumns" style="background-color: #FFFFFF; border-top: 1px solid #FFFFFF;border-bottom: 1px solid #CCCCCC; border: 1px solid #BBBBBB;border-collapse: collapse !important;">
                                                <tr>
                                                    {payload}
                                                </tr>
                                            </table>
                                        </tr>
                                        <tr>
                                            <td valign="top" align="center" class="footerContent" style="width:100%; font-size: 14px; font-family:Helvetica; color: #606060; text-align: center;">
                                                <a href="https://ui.adsabs.harvard.edu/" style="color: #606060;">Search ADS</a>&nbsp;&nbsp;&nbsp;<a href="" style="color: #606060;">myADS settings</a>&nbsp;
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                                <td align="center" valign="top">
                                    <table border="0" cellpadding="20" cellspacing="0" width="100%" id="emailFooter" style="color: #999999; font-size: 12px; text-align: center; font-family: Helvetica;">
                                        <tr>
                                            <td align="center" valign="top">
                                                <p> This message was sent to {email_address}. </p>
                                                <p> &copy; SAO/NASA <a href="https://ui.adsabs.harvard.edu">Astrophysics Data System</a> <br> 60 Garden Street <br> Cambridge, MA</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
    </html>
"""

class Email(object):
    """
    Data structure that contains email content data
    """
    msg_plain = ''
    msg_html = ''
    subject = ''
    salt = ''

class myADSTemplate(Email):
    """
    myADS email template
    """

    msg_plain = """
        SAO/NASA ADS: myADS Personal Notification Service Results
    
        {payload}
        """
    msg_html = html_template
    subject = 'myADS Notification'